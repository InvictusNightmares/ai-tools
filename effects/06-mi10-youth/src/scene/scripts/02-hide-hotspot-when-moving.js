/* Scene behavior: hide-hotspot-when-moving. Registered in original execution order. */
var HideHotspotWhenMoving = pc.createScript("hideHotspotWhenMoving");
HideHotspotWhenMoving.attributes.add("hotspotEntitys", {
  type: "entity",
  array: true,
});
HideHotspotWhenMoving.prototype.initialize = function () {
  this.needSetHotSpot = false;
  this.app.mouse &&
    (this.app.mouse.on(pc.EVENT_MOUSEDOWN, this.onMouseDown, this),
    this.app.mouse.on(pc.EVENT_MOUSEUP, this.onMouseUp, this),
    this.app.mouse.on(pc.EVENT_MOUSEMOVE, this.onMouseMove, this));
  this.app.touch &&
    (this.app.touch.on(pc.EVENT_TOUCHSTART, this.onTouchStart, this),
    this.app.touch.on(pc.EVENT_TOUCHEND, this.onTouchEnd, this),
    this.app.touch.on(pc.EVENT_TOUCHMOVE, this.onTouchMove, this));
};
HideHotspotWhenMoving.prototype.update = function (t) {};
HideHotspotWhenMoving.prototype.onMouseDown = function (t) {
  this.needSetHotSpot = true;
};
HideHotspotWhenMoving.prototype.onMouseUp = function (t) {
  this.needSetHotSpot = false;
  for (var o = 0; o < this.hotspotEntitys.length; o++)
    this.hotspotEntitys[o].enabled = true;
};
HideHotspotWhenMoving.prototype.onMouseMove = function (t) {
  if (this.needSetHotSpot) {
    this.needSetHotSpot = false;
    for (var o = 0; o < this.hotspotEntitys.length; o++)
      this.hotspotEntitys[o].enabled = false;
  }
};
HideHotspotWhenMoving.prototype.onTouchStart = function (t) {
  1 === t.touches.length && (this.needSetHotSpot = true);
};
HideHotspotWhenMoving.prototype.onTouchEnd = function (t) {
  if (0 === t.touches.length) {
    this.needSetHotSpot = false;
    for (var o = 0; o < this.hotspotEntitys.length; o++)
      this.hotspotEntitys[o].enabled = true;
  }
};
HideHotspotWhenMoving.prototype.onTouchMove = function (t) {
  if (1 === t.touches.length && this.needSetHotSpot) {
    this.needSetHotSpot = false;
    for (var o = 0; o < this.hotspotEntitys.length; o++)
      this.hotspotEntitys[o].enabled = false;
  }
};
