/* Scene behavior: touch-input. Registered in original execution order. */
var TouchInput = pc.createScript("touchInput");
TouchInput.attributes.add("orbitSensitivity", {
  type: "number",
  default: 0.4,
  title: "Orbit Sensitivity",
  description: "How fast the camera moves around the orbit. Higher is faster",
});
TouchInput.attributes.add("distanceSensitivity", {
  type: "number",
  default: 0.2,
  title: "Distance Sensitivity",
  description: "How fast the camera moves in and out. Higher is faster",
});
TouchInput.prototype.initialize = function () {
  this.orbitCamera = this.entity.script.orbitCamera;
  this.lastTouchPoint = new pc.Vec2();
  this.lastPinchMidPoint = new pc.Vec2();
  this.lastPinchDistance = 0;
  this.orbitCamera &&
    this.app.touch &&
    (this.app.touch.on(pc.EVENT_TOUCHSTART, this.onTouchStartEndCancel, this),
    this.app.touch.on(pc.EVENT_TOUCHEND, this.onTouchStartEndCancel, this),
    this.app.touch.on(pc.EVENT_TOUCHCANCEL, this.onTouchStartEndCancel, this),
    this.app.touch.on(pc.EVENT_TOUCHMOVE, this.onTouchMove, this),
    this.on("destroy", function () {
      this.app.touch.off(pc.EVENT_TOUCHSTART, this.onTouchStartEndCancel, this);
      this.app.touch.off(pc.EVENT_TOUCHEND, this.onTouchStartEndCancel, this);
      this.app.touch.off(
        pc.EVENT_TOUCHCANCEL,
        this.onTouchStartEndCancel,
        this,
      );
      this.app.touch.off(pc.EVENT_TOUCHMOVE, this.onTouchMove, this);
    }));
};
TouchInput.prototype.getPinchDistance = function (t, i) {
  var o = t.x - i.x,
    n = t.y - i.y;
  return Math.sqrt(o * o + n * n);
};
TouchInput.prototype.calcMidPoint = function (t, i, o) {
  o.set(i.x - t.x, i.y - t.y);
  o.scale(0.5);
  o.x += t.x;
  o.y += t.y;
};
TouchInput.prototype.onTouchStartEndCancel = function (t) {
  var i = t.touches;
  1 == i.length
    ? this.lastTouchPoint.set(i[0].x, i[0].y)
    : 2 == i.length &&
      ((this.lastPinchDistance = this.getPinchDistance(i[0], i[1])),
      this.calcMidPoint(i[0], i[1], this.lastPinchMidPoint));
};
TouchInput.fromWorldPoint = new pc.Vec3();
TouchInput.toWorldPoint = new pc.Vec3();
TouchInput.worldDiff = new pc.Vec3();
TouchInput.prototype.pan = function (t) {
  var i = TouchInput.fromWorldPoint,
    o = TouchInput.toWorldPoint,
    n = TouchInput.worldDiff,
    c = this.entity.camera,
    h = this.orbitCamera.distance;
  c.screenToWorld(TouchInput.beginScreenPoint.x, t.y, h, i);
  c.screenToWorld(
    TouchInput.beginScreenPoint.x,
    this.lastPinchMidPoint.y,
    h,
    o,
  );
  n.sub2(o, i);
  this.orbitCamera.pivotPoint.add(n);
};
TouchInput.pinchMidPoint = new pc.Vec2();
TouchInput.prototype.onTouchMove = function (t) {
  if (toogleCameraRotate) {
    var i = TouchInput.pinchMidPoint,
      o = t.touches;
    if (1 == o.length) {
      var n = o[0];
      toogleCameraPitch &&
        (this.orbitCamera.pitch -=
          (n.y - this.lastTouchPoint.y) * this.orbitSensitivity);
      this.orbitCamera.yaw -=
        (n.x - this.lastTouchPoint.x) * this.orbitSensitivity;
      this.lastTouchPoint.set(n.x, n.y);
    } else if (2 == o.length) {
      var c = this.getPinchDistance(o[0], o[1]),
        h = c - this.lastPinchDistance;
      this.lastPinchDistance = c;
      this.orbitCamera.distance -=
        h * this.distanceSensitivity * 0.1 * (0.1 * this.orbitCamera.distance);
      this.calcMidPoint(o[0], o[1], i);
      this.orbitCamera.panning && this.pan(i);
      this.lastPinchMidPoint.copy(i);
    }
  }
};
