# 小米 10 青春版 WebGL 源码

参考页面：<https://s1.mi.com/m/webgl/mi10Yjd/>

这是根据公开页面还原的可编辑源码工程，保留原页的模型、贴图、米兰字体、镜头参数和动画时序。包含桌面开盒、360° 外观、五种配色、内部拆解、潜望式变焦、样片图集和五段演示视频。

这里只交付源码、原始素材和构建配置。`dist/` 是执行构建命令后才生成的目录，已加入忽略规则。PlayCanvas 通过 npm 固定为原站的 `1.26.1` 版本，不在源码目录保留压缩引擎文件。

## 本地开发

需要 Node.js 22 或更高版本。

```bash
cd /Users/invictus/Github/ai-tools/effects/06-mi10-youth
npm ci
npm run dev
```

打开 <http://127.0.0.1:8766>。修改 `src/` 后刷新浏览器即可生效，不需要先构建。端口可用 `npm run dev -- --port 9000` 修改。

## 源码入口

| 路径 | 内容 |
| --- | --- |
| `src/index.html` | 页面结构、按钮、视频和图集 |
| `src/canvas.html` | 3D 场景页面和引擎初始化配置 |
| `src/styles/` | 展开后的页面、画布和加载样式 |
| `src/ui/` | 9 个交互源码文件：导航、文案、换色、变焦、开盒、视频、图集 |
| `src/runtime/` | 应用启动、输入设备、加载进度 |
| `src/scene/scripts/` | 37 个场景行为文件，包括补间动画、相机、材质、拆解、开盒和资源加载 |
| `src/scene/scene.json` | 可编辑的实体层级、位置、旋转、镜头和脚本参数 |
| `src/scene/config.json` | 素材、材质、脚本注册信息 |
| `public/` | 原始模型、贴图、字体、按钮、样片和视频 |
| `scripts/entries.json` | 源码文件的加载顺序 |
| `asset-manifest.json` | 每个原始素材的来源、大小和 SHA-256 |

常用修改位置：

- 开盒镜头：`src/scene/scripts/22-controller-camera.js`、`23-controller-boxs.js`、`24-open-box.js`，以及 `src/ui/05-unboxing.js`。
- 拖拽旋转：`src/scene/scripts/03-touch-input.js`、`04-orbit-camera.js`、`05-mouse-input.js`。
- 配色：`src/ui/03-color-picker.js`、`src/scene/scripts/08-ext-color-manager.js`。
- 拆解：`src/scene/scripts/12-blast-model.js`。
- 变焦：`src/ui/04-zoom-slider.js`、`src/scene/scripts/28-distance-zoom.js`。
- 文案和排版：`src/index.html`、`src/ui/01-hotspot-copy.js`、`src/styles/ui.css`。

这些文件保留原页经典脚本的共享作用域。开发服务按 `entries.json` 合并源码后直接响应给浏览器；构建时才生成运行文件。这样保留 PlayCanvas 脚本之间及页面与 iframe 之间的调用顺序。添加源码文件时，将它加入相应入口列表。

## 构建

```bash
npm run build
npm run preview
```

构建会生成可独立托管的 `dist/`，预览地址为 <http://127.0.0.1:8767>。所有视觉资源在本地，运行不需要请求小米 CDN。视频支持 HTTP Range。购物链接保留原页指向京东的行为。

使用 HTTP 服务打开页面，不能直接双击 HTML：场景 JSON、iframe 同源通信和模型加载需要 HTTP 环境。

## 还原范围

交互源码已解开字符串混淆并按行为分文件，样式和场景 JSON 已展开；公开发布包未包含作者原始变量名、PlayCanvas 编辑器工程或建模源文件，因此这些不是小米内部原始工程。模型为原站使用的网格数据，材质和贴图保持原样。

原页会随机选择包装盒图案，且动画随时间推进，截图比较应在相同视口、状态和时间点进行。未添加额外导航或装饰，保留原页视觉。

移除了百度统计、绑定小米域名的微信分享、未使用的 jQuery，以及原站已返回 404 的旧加载脚本和 manifest 引用。现用加载动画保留。其余调整为资源路径、HTML 无效结束标签和初始化前 resize 的保护判断。

页面图片、模型、文案、视频和字体的权利归原权利人所有；PlayCanvas 为 MIT 许可。素材来源详见清单。

## 本次验证

2026-09-06：开发源码和构建结果均已在浏览器运行。检查了桌面视口与 375 × 812 窄屏，开盒、拖拽旋转、配色变化、内部拆解、变焦倍率与画面联动、相机介绍和样片页可用；视频实际播放超过 20 秒，无播放错误。检查期间浏览器没有 JavaScript 错误或警告。

211 个本地原始素材通过 SHA-256 核对，275 项场景资源配置均能解析到本地文件或源码入口。构建通过后已删除 `dist/` 和 `node_modules/`，交付目录保留 48 个 JavaScript 源文件。未做逐帧像素差分析，也未做真机触摸测试。
