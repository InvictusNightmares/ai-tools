/* Scene behavior: distance-zoom. Registered in original execution order. */
var DistanceZoom = pc.createScript("distanceZoom");
DistanceZoom.attributes.add("minDistance_vert", {
  type: "number",
  default: 5,
  title: "min distance vert",
});
DistanceZoom.attributes.add("maxDistance_vert", {
  type: "number",
  default: 8,
  title: "max distance vert",
});
DistanceZoom.attributes.add("minDistance_horz", {
  type: "number",
  default: 10,
  title: "min distance horz",
});
DistanceZoom.attributes.add("maxDistance_horz", {
  type: "number",
  default: 16,
  title: "max distance horz",
});
DistanceZoom.attributes.add("sensitivity", {
  type: "number",
  default: 1,
});
DistanceZoom.attributes.add("inertia", {
  type: "number",
  default: 0,
});
DistanceZoom.attributes.add("setPauseEvent", {
  type: "string",
  default: "pauseCam:ext",
});
DistanceZoom.prototype.initialize = function () {
  this.app.graphicsDevice.width / this.app.graphicsDevice.height < 1
    ? this.setVerticalDistance()
    : this.setHorizontalDistance();
  var t = this;
  window.addEventListener("resize", function () {
    t.app.graphicsDevice.width / t.app.graphicsDevice.height < 1
      ? t.setVerticalDistance()
      : t.setHorizontalDistance();
  });
  this.app.on(this.setPauseEvent, this.onSetPause, this);
  var i = new pc.Vec3();
  i.sub2(
    this.entity.getPosition().clone(),
    this.entity.parent.getPosition().clone(),
  );
  this.distance = this.clampDistance(i.length());
  this.app.mouse && this.app.mouse.on(pc.EVENT_MOUSEWHEEL, this.onZoom, this);
  this.app.touch &&
    (this.app.touch.on(pc.EVENT_TOUCHSTART, this.onTouchStartEndCancel, this),
    this.app.touch.on(pc.EVENT_TOUCHEND, this.onTouchStartEndCancel, this),
    this.app.touch.on(pc.EVENT_TOUCHCANCEL, this.onTouchStartEndCancel, this),
    this.app.touch.on(pc.EVENT_TOUCHMOVE, this.onTouchMove, this));
  this.lastTouchPoint = new pc.Vec2();
  this.lastPinchMidPoint = new pc.Vec2();
  this.lastPinchDistance = 0;
  this.targetDistance = (this.minDistance + this.maxDistance) / 2;
  this.bPauseControl = false;
  this.app.on(
    "zoom_camera_whenOpenHotspot",
    this.zoomCamDistance_hotspot,
    this,
  );
};
DistanceZoom.prototype.update = function (t) {
  var i = 0 === this.inertia ? 1 : Math.min(t / this.inertia, 1);
  this.distance = pc.math.lerp(this.distance, this.targetDistance, i);
  var e = this.entity.getPosition();
  e.copy(this.entity.forward);
  e.scale(-this.distance);
  e.add(this.entity.parent.getPosition());
  this.entity.setPosition(e);
};
DistanceZoom.prototype.zoomCamDistance_hotspot = function () {
  this.targetDistance = this.minDistance;
  this.targetDistance = this.clampDistance(this.targetDistance);
};
DistanceZoom.prototype.onSetPause = function (t) {
  this.bPauseControl = t;
};
DistanceZoom.prototype.onZoom = function (t) {
  this.entity.enabled &&
    ((this.targetDistance -=
      t.wheel * this.sensitivity * (0.1 * this.distance)),
    (this.targetDistance = this.clampDistance(this.targetDistance)));
};
DistanceZoom.prototype.clampDistance = function (t) {
  return this.maxDistance > 0
    ? pc.math.clamp(t, this.minDistance, this.maxDistance)
    : Math.max(t, this.minDistance);
};
DistanceZoom.prototype.onTouchStartEndCancel = function (t) {
  if (this.entity.enabled) {
    var i = t.touches;
    2 == i.length &&
      (this.lastPinchDistance = this.getPinchDistance(i[0], i[1]));
  }
};
DistanceZoom.prototype.onTouchMove = function (t) {
  if (!this.bPauseControl) {
    var i = t.touches;
    if (2 == i.length) {
      var e = this.getPinchDistance(i[0], i[1]),
        s = e - this.lastPinchDistance;
      this.lastPinchDistance = e;
      this.targetDistance -= s * this.sensitivity * 0.1 * (0.1 * this.distance);
      this.targetDistance = this.clampDistance(this.targetDistance);
    }
  }
};
DistanceZoom.prototype.getPinchDistance = function (t, i) {
  var e = t.x - i.x,
    s = t.y - i.y;
  return Math.sqrt(e * e + s * s);
};
DistanceZoom.prototype.setVerticalDistance = function () {
  this.minDistance = 2.4 * this.minDistance_vert;
  this.maxDistance = 2 * this.maxDistance_vert;
  this.targetDistance = (this.minDistance + this.maxDistance) / 2;
};
DistanceZoom.prototype.setHorizontalDistance = function () {
  this.minDistance = this.minDistance_horz;
  this.maxDistance = this.maxDistance_horz;
  this.targetDistance = (this.minDistance + this.maxDistance) / 2;
};
