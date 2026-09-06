/* UI behavior: hotspot-copy. Plain source, shared classic-script scope. */
function intload(_state) {
  if (_state == 0) {
    document.getElementById("loadintbg").style.display = "block";
    document.getElementById("loadintimg").style.opacity = "0.5";
  } else {
    document.getElementById("loadintbg").style.display = "none";
  }
}
var HotA_Title = [
  "Tittle ",
  "JNCD<0.7丨 delta E 1.1<br>莱茵低蓝光护眼认证",
  "石墨覆盖重点芯片，快速散热<br>8颗温度传感器，智能温控",
  "7nmEUV 工艺<br>集成式 SA/NSA 双模5G",
  "20W 极速快充<br>手机快速回血",
  "机械齿轮般的震感",
  "响度大、音域广",
];
var HotA_Text = [
  "Text",
  "旗舰屏幕体验，精准的色彩表现，尤其适合修图调色。180Hz 采样率，提升操控灵敏度。支持HDR 10+ ，阳光屏、硬件级 DC 调光，无论强光弱光，看什么都舒服。",
  "石墨烯 + 多层石墨 + 悬浮液冷 + 导热凝胶，结合创新的悬浮结构，散热效率更胜以往。长时间拿在手里刷剧玩游戏，依然流畅不发热。",
  "先进的制程工艺，使得算力、渲染、AI突飞猛进，能耗却一降再降。全频段双模5G 配合小米独家 MultiLink 三网无缝并连技术，确保网络更快更稳定。",
  "标配 22.5W 有线充电器，符合 QC 4.0 快充协议。续航持久、回血迅速，从容应对一整天日常使用。",
  "灵动丰富的立体震感体验，上手即上瘾。",
  "让纤薄的机身也能拥有宽广浑厚的声音， 看电影、听音乐，引人入胜，忘怀其中。",
];
var HotB_Title = [
  "Tittle ",
  "See beautiful details <br> from afar",
  "Show your beauty <br> in-depth",
  "Upgraded 108MP <br>AI 8K",
  "Broad and wide view <br> within your lens",
];
var HotB_Text = [
  "Text",
  "From intermediate to long-range zoom, the image is always clear and sharp.",
  "Classic 50mm focal length, close to the field of view of our own eyes. Progressive image processing creates natural bokeh effect.",
  "108MP meets advanced algorithms for improved image quality, user experience, and the power to capture 8K video.",
  "Create your own masterpieces featuring grand architecture and stunning nature, and with no more worries of leaving anyone out when you shoot group photos.",
];
function uiscaleCshow() {
  document.getElementById("uiscaleC").style.right = "0px";
}
function uiscaleChide() {
  document.getElementById("uiscaleC").style.right = "";
}
function funcHotA(_visible, _hotspotIndex) {
  if (_visible == true) {
    uiscaleCshow();
  } else {
    uiscaleChide();
  }
  if (_hotspotIndex == 5) {
    document.getElementById("Ctittle").style.marginTop = "30px";
  } else {
    document.getElementById("Ctittle").style.marginTop = "20px";
  }
  TextX(0);
  document.getElementById("Ctittle").innerHTML = HotA_Title[_hotspotIndex];
  document.getElementById("Ctext").innerHTML = HotA_Text[_hotspotIndex];
}
function funcHotB(_visible2, _hotspotIndex2) {}
function launchIntoFullscreen(_element) {
  if (_element.requestFullscreen) {
    _element.requestFullscreen();
  } else if (_element.mozRequestFullScreen) {
    _element.mozRequestFullScreen();
  } else if (_element.webkitRequestFullscreen) {
    _element.webkitRequestFullscreen();
  } else if (_element.msRequestFullscreen) {
    _element.msRequestFullscreen();
  }
}
function exitFullscreen() {
  if (document.exitFullscreen) {
    document.exitFullscreen();
  } else if (document.mozCancelFullScreen) {
    document.mozCancelFullScreen();
  } else if (document.webkitExitFullscreen) {
    document.webkitExitFullscreen();
  }
}
