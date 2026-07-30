import json
import re
import ssl
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib import error, request

INPUT_FILE = "url.txt"
OUTPUT_FILE = "data_records.txt"
USABLE_OUTPUT_FILE = "usable_data_records.txt"
API_KEY = "your-api-key-2"
TIMEOUT_SECONDS = 12
MAX_WORKERS = 20  # 最大线程数
TARGET_MODEL_KEYWORD = "claude"
TEST_MAX_TOKENS = 1

URL_RE = re.compile(r"https?://[^\s\"']+")


def normalize_url(raw: str) -> str:
    line = raw.strip()
    if not line or line.startswith("#"):
        return ""

    match = URL_RE.search(line)
    if not match:
        return ""

    url = match.group(0).rstrip("/").rstrip('",')
    for suffix in ("/v1/models", "/v1/chat/completions", "/v1/completions", "/v1"):
        if url.endswith(suffix):
            url = url[: -len(suffix)]
            break
    return url.rstrip("/")


def make_ssl_context() -> ssl.SSLContext:
    """创建忽略 SSL 验证的上下文，兼容自签证书代理。"""
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    return ssl_context


def safe_read_body(resp: object) -> tuple[str, str | None]:
    """读取响应体；如果服务端卡住或断开，不让单个 URL 中断全局任务。"""
    try:
        body = resp.read().decode("utf-8", errors="replace")
    except Exception as e:  # noqa: BLE001
        return "", f"读取响应体失败: {e}"
    return body, None


def fetch_models(base_url: str) -> dict:
    """获取模型信息，返回包含结果的字典"""
    models_url = f"{base_url}/v1/models"

    req = request.Request(
        models_url,
        method="GET",
        headers={"Authorization": f"Bearer {API_KEY}"},
    )

    result = {
        "url": models_url,
        "base_url": base_url,
        "success": False,
        "status": None,
        "response": None,
        "error": None,
    }

    try:
        with request.urlopen(req, timeout=TIMEOUT_SECONDS, context=make_ssl_context()) as resp:
            body, read_error = safe_read_body(resp)
            result["status"] = resp.status
            result["success"] = True
            result["body"] = body
            if read_error:
                result["error"] = read_error
    except error.HTTPError as e:
        body, read_error = safe_read_body(e)
        result["status"] = e.code
        result["body"] = body
        result["success"] = True  # HTTP 错误也可能带有可解析响应体
        if read_error:
            result["error"] = f"HTTP {e.code} {e.reason}; {read_error}"
    except Exception as e:  # noqa: BLE001
        result["error"] = str(e)

    return result


def get_matching_models(payload: object) -> list[str]:
    """提取包含目标关键字的模型 ID。"""
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        return []

    models: list[str] = []
    seen: set[str] = set()
    for item in payload["data"]:
        if not isinstance(item, dict):
            continue

        model_id = item.get("id")
        if not isinstance(model_id, str):
            continue

        if TARGET_MODEL_KEYWORD in model_id and model_id not in seen:
            models.append(model_id)
            seen.add(model_id)

    return models


def test_model(base_url: str, model: str) -> tuple[bool, str | None]:
    """对模型做一次最小 chat completions 请求，返回 (是否可用, 错误信息)。"""
    test_url = f"{base_url}/v1/chat/completions"
    body = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": "hi"}],
            "max_tokens": TEST_MAX_TOKENS,
            "stream": False,
        }
    ).encode("utf-8")
    req = request.Request(
        test_url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json",
        },
    )

    try:
        with request.urlopen(req, timeout=TIMEOUT_SECONDS, context=make_ssl_context()) as resp:
            response_body = resp.read().decode("utf-8", errors="replace")
            if not 200 <= resp.status < 300:
                return False, f"HTTP {resp.status}"

            try:
                payload = json.loads(response_body)
            except json.JSONDecodeError:
                return False, "测试接口返回非 JSON"

            if isinstance(payload, dict) and (
                isinstance(payload.get("choices"), list) or payload.get("object")
            ):
                return True, None

            return False, "测试接口响应格式异常"
    except error.HTTPError as e:
        body_text, read_error = safe_read_body(e)
        body_text = body_text.strip()
        detail = body_text[:200] if body_text else e.reason
        if read_error:
            detail = f"{detail}; {read_error}"
        return False, f"HTTP {e.code}: {detail}"
    except Exception as e:  # noqa: BLE001
        return False, str(e)


def test_any_matching_model(base_url: str, models: list[str]) -> tuple[bool, str | None]:
    """只要任意一个匹配模型能完成最小请求，就认为该 URL 可用。"""
    last_error: str | None = None
    for model in models:
        usable, test_error = test_model(base_url, model)
        if usable:
            return True, None
        last_error = f"{model}: {test_error}"
    return False, last_error


def format_result_line(item: dict) -> str:
    return "-".join([item["url"], item["status_text"], *item["models"]])


def process_result(result: dict) -> tuple[dict | None, dict | None]:
    """处理单个请求结果，返回 (matched_item, failed_item)"""
    full_url = result["url"]
    base_url = result["base_url"]

    if result["error"]:
        failed_item = {"url": full_url, "error": result["error"]}
        print(f"[FAIL] {full_url} -> {result['error']}")
        return None, failed_item

    try:
        payload = json.loads(result.get("body") or "")
    except json.JSONDecodeError:
        failed_item = {"url": full_url, "error": f"非 JSON 响应 (status={result['status']})"}
        print(f"[FAIL] {full_url} -> 非 JSON 响应")
        return None, failed_item

    models = get_matching_models(payload)
    if not models:
        print(f"[SKIP] {full_url} -> 无 {TARGET_MODEL_KEYWORD} 模型")
        return None, None

    usable, test_error = test_any_matching_model(base_url, models)
    status_text = "可用" if usable else "不可用"
    matched_item = {
        "url": base_url,
        "usable": usable,
        "status_text": status_text,
        "models": models,
        "test_error": test_error,
    }
    print(f"[OK]   {full_url} -> {status_text}，模型: {', '.join(models)}")
    if test_error:
        print(f"       测试失败原因: {test_error}")
    return matched_item, None


def main() -> None:
    input_path = Path(INPUT_FILE)
    output_path = Path(OUTPUT_FILE)
    usable_output_path = Path(USABLE_OUTPUT_FILE)

    if not input_path.exists():
        raise FileNotFoundError(f"未找到输入文件: {input_path}")

    urls = [normalize_url(line) for line in input_path.read_text(encoding="utf-8").splitlines()]
    urls = sorted({u for u in urls if u})

    print(f"开始处理 {len(urls)} 个 URL，使用 {MAX_WORKERS} 个线程...\n")

    matched: list[dict] = []
    failed: list[dict] = []

    # 使用线程池并发执行
    with (
        output_path.open("w", encoding="utf-8") as output_file,
        usable_output_path.open("w", encoding="utf-8") as usable_output_file,
        ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor,
    ):
        future_to_url = {executor.submit(fetch_models, url): url for url in urls}

        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                result = future.result()
            except Exception as e:  # noqa: BLE001
                failed.append({"url": f"{url}/v1/models", "error": str(e)})
                print(f"[FAIL] {url}/v1/models -> {e}")
                continue

            matched_item, failed_item = process_result(result)

            if matched_item:
                matched.append(matched_item)
                output_file.write(format_result_line(matched_item))
                output_file.write("\n")
                output_file.flush()

                if matched_item["usable"]:
                    usable_output_file.write(f"{matched_item['url']}\n")
                    usable_output_file.flush()

            if failed_item:
                failed.append(failed_item)

    failed.sort(key=lambda x: x["url"])

    print("\n" + "=" * 50)
    print("完成。")
    print(f"总 URL 数: {len(urls)}")
    print(f"包含 {TARGET_MODEL_KEYWORD} 的 URL 数: {len(matched)}")
    print(f"可用数: {sum(1 for item in matched if item['usable'])}")
    print(f"不可用数: {sum(1 for item in matched if not item['usable'])}")
    print(f"失败数: {len(failed)}")
    print(f"结果文件: {output_path.resolve()}")
    print(f"可用结果文件: {usable_output_path.resolve()}")

    # 如果有失败，打印失败列表
    if failed:
        print("\n失败列表:")
        for item in failed[:10]:  # 只显示前10个
            print(f"  - {item['url']}: {item['error']}")
        if len(failed) > 10:
            print(f"  ... 还有 {len(failed) - 10} 个失败")


if __name__ == "__main__":
    main()
