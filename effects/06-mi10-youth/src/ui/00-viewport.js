/* UI behavior: viewport. Plain source, shared classic-script scope. */
var orientation =
  screen.msOrientation ||
  screen.mozOrientation ||
  (screen.orientation || {}).type;
var mode = 0;
var pc = 0;
var pzmode = 0;
var hp = 0;
var intonx = 0;
var windowWidth = 0;
function getSizew() {
  windowWidth = window.innerWidth;
  var _portraitQuery = window.matchMedia("(orientation:portrait)");
  var _userAgent = navigator.userAgent;
  var _mobileDevices = new Array("Android", "iPhone", "Windows Phone", "iPad");
  var _value = true;
  for (var _value2 = 0; _value2 < _mobileDevices.length; _value2++) {
    if (_userAgent.indexOf(_mobileDevices[_value2]) > 0) {
      _value = false;
      break;
    }
  }
  if (/(iPhone|Android|Windows Phone )/i.test(navigator.userAgent)) {
    if (_portraitQuery.matches == true) {
      mode = 5;
    } else {
      mode = 6;
    }
  } else {
    if (windowWidth > 1900) {
      mode = 0;
    } else if (windowWidth > 1400) {
      mode = 1;
    } else if (windowWidth > 1200) {
      mode = 2;
    } else if (windowWidth > 1000) {
      mode = 3;
    } else {
      mode = 4;
    }
  }
  document.getElementById("uiscaleB").style.transform = "translate(0px,20px) ";
  document.getElementById("closex").style.transform =
    "translate(0px,0px)  scale(0.7)";
  document.getElementById("Ctext").style =
    "margin-top: 15px; margin-left: 20px; font-size: 13px; ";
  document.getElementById("btnC_01").style =
    "font-size:18px; transform: translate(10px,-50px) scale(0.7); margin-right: 0px;";
  document.getElementById("Cline").style =
    "transform: translate(10px,-20px) scale(1); width:1px; margin-right: 0px;";
  TextX(xx);
  switch (mode) {
    case 0:
      break;
    case 1:
      break;
    case 2:
      break;
    case 3:
      break;
    case 4:
      break;
    case 5:
      break;
    case 6:
      break;
    default:
  }
  return _value;
}
getSizew();
var iframe = document.getElementById("iframe");
var iframeF = document.getElementById("floathtml");
