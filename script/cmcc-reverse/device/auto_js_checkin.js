// AutoX.js / Auto.js check-in script for a non-root Android phone.
// The phone must already be logged in to the China Mobile app.
// Run with AutoX.js accessibility permission; schedule daily inside AutoX.js.

auto.waitFor();

var PACKAGE = "com.greenpoint.android.mc10086.activity";
var HOME_ENTRY = "签到有礼";
var SIGN_RE = /立即签到|补签|签到/;

function toastMsg(msg) {
    toast(msg);
    console.log(msg);
}

toastMsg("启动中国移动");
app.launch(PACKAGE);
sleep(7000);

var home = textContains(HOME_ENTRY).findOnce();
if (!home) {
    toastMsg("未找到签到有礼，检查页面/分辨率");
    exit();
}
home.click();
sleep(5000);

var sign = textMatches(SIGN_RE).findOnce();
if (!sign) {
    // WebView 有时不暴露文本，退回到坐标/图片匹配。
    // 用当前手机截图确定坐标后，把下面两行改成 click(x, y)。
    toastMsg("未找到签到按钮，请改用坐标或 uiautomator");
    exit();
}

toastMsg("点击 " + sign.text());
sign.click();
sleep(3000);
toastMsg("签到脚本结束");
