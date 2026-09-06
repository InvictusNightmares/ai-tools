/* Loading progress and the original responsive loading animation. */
var mode = 0;
function getSizew() {
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
    var _innerWidth = window.innerWidth;
    if (_innerWidth > 1900) {
      mode = 0;
    } else if (_innerWidth > 1400) {
      mode = 1;
    } else if (_innerWidth > 1200) {
      mode = 2;
    } else if (_innerWidth > 1000) {
      mode = 3;
    } else {
      mode = 4;
    }
  }
  document.getElementById("loadinint").style.width = "250px";
  document.getElementById("loadinint").style.transform =
    "translate(-50%,-50%)  scale(0.8)";
  document.getElementById("loadnumberbar").style.height = "5px";
  document.getElementById("loadnumberbg").style.height = "5px";
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
      document.getElementById("loadinint").style.width = "200px";
      document.getElementById("loadinint").style.transform =
        "translate(-50%,-50%)  scale(0.8)";
      document.getElementById("loadnumberbar").style.height = "4px";
      document.getElementById("loadnumberbg").style.height = "4px";
      break;
    case 6:
      document.getElementById("loadinint").style.width = "200px";
      document.getElementById("loadinint").style.transform =
        "translate(-50%,50px)  scale(0.8)";
      document.getElementById("loadnumberbar").style.height = "4px";
      document.getElementById("loadnumberbg").style.height = "4px";
      break;
    default:
  }
  return _value;
}
getSizew();
var app = pc.Application.getApplication();
function Load() {
  document.getElementById("loadframeint").style.display = "block";
  function _value3(_value5) {
    var _loadnumberbarElement = document.getElementById("loadnumberbar");
    var _loadnumberElement = document.getElementById("loadnumber");
    if (_loadnumberbarElement) {
      _value5 = Math.round(_value5 * 100);
      _loadnumberbarElement.style.width = _value5 + "%";
      _loadnumberElement.innerHTML = _value5 + "%";
    }
  }
  function _value4() {
    setTimeout(function () {
      document.getElementById("loadframeint").style.opacity = "0";
    }, 1500);
    setTimeout(function () {
      document.getElementById("loadframeint").style.display = "none";
    }, 2000);
  }
  app.on("start", _value4);
  app.on("preload:progress", _value3);
}
function intnumbx(_progress) {
  switch (_progress) {
    case 1:
      intloadx = 1;
      document.getElementById("loadnumber").innerHTML = "15%";
      document.getElementById("loadnumberbar").style.width = "30px";
      break;
    case 2:
      document.getElementById("loadnumber").innerHTML = "32%";
      document.getElementById("loadnumberbar").style.width = "64px";
      break;
    case 3:
      document.getElementById("loadnumber").innerHTML = "48%";
      document.getElementById("loadnumberbar").style.width = "96px";
      break;
    case 4:
      document.getElementById("loadnumber").innerHTML = "64%";
      document.getElementById("loadnumberbar").style.width = "128px";
      break;
    case 5:
      document.getElementById("loadnumber").innerHTML = "80%";
      document.getElementById("loadnumberbar").style.width = "160px";
      break;
    case 6:
      document.getElementById("loadnumber").innerHTML = "100%";
      document.getElementById("loadnumberbar").style.width = "200px";
      setTimeout(function () {
        document.getElementById("loadframeint").style.display = "none";
      }, 300);
      break;
    default:
      document.getElementById("loadnumberbar").innerHTML = "0%";
  }
}
