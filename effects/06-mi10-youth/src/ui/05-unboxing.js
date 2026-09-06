/* UI behavior: unboxing. Plain source, shared classic-script scope. */
function UIon() {
  document.getElementById("ALL").style.display = "block";
  document.getElementById("openbtn").style.display = "block";
  document.getElementById("openbtn").style.transition = "0s";
  document.getElementById("openbtn").style.opacity = "0";
  setTimeout(function () {
    openfunc();
  }, 100);
}
function openfunc() {
  try {
    iframe.contentWindow.app.fire("cam_beginRotate");
  } catch (_value26) {}
  setTimeout(function () {
    document.getElementById("openbtn").style.transition = "1s";
    document.getElementById("openbtn").style.opacity = "0.8";
  }, 3000);
}
document.getElementById("openbtn").onclick = function () {
  try {
    iframe.contentWindow.app.fire("cam_openBox");
  } catch (_value27) {}
  document.getElementById("openbtn").style.opacity = "0";
  setTimeout(function () {
    document.getElementById("openbtn").style.display = "none";
    document.getElementById("ALL").style.transition = "1s";
    document.getElementById("ALL").style.opacity = "1";
  }, 2500);
};
var vid_width = 0;
var imgid = 1;
var imgidB = 1;
var position1 = 0;
var position2 = 0;
var position3 = 0;
var positionB1 = 0;
var positionB2 = 0;
var positionB3 = 0;
var image_1x = document.getElementById("image_1");
var image_2x = document.getElementById("image_2");
var image_3x = document.getElementById("image_3");
var imageB_1x = document.getElementById("imageB_1");
var imageB_2x = document.getElementById("imageB_2");
var imageB_3x = document.getElementById("imageB_3");
