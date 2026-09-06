/* Scene behavior: platform-check. Registered in original execution order. */
var PlatformCheck = pc.createScript("platformCheck");
function IsPC() {
  for (
    var t = navigator.userAgent,
      e = ["Android", "iPhone", "SymbianOS", "Windows Phone", "iPad", "iPod"],
      o = true,
      i = 0;
    i < e.length;
    i++
  )
    if (t.indexOf(e[i]) > 0) {
      o = false;
      break;
    }
  return o;
}
PlatformCheck.prototype.initialize = function () {};
PlatformCheck.prototype.update = function (t) {};
