/* Scene behavior: orbit-camera-control. Registered in original execution order. */
var OrbitCameraControl = pc.createScript("orbitCameraControl");
OrbitCameraControl.attributes.add("sensivity", {
  type: "number",
  default: 0.5,
});
OrbitCameraControl.attributes.add("easing", {
  type: "number",
  default: 0.2,
});
OrbitCameraControl.attributes.add("pitchAxisMax", {
  type: "number",
  default: 75,
});
OrbitCameraControl.attributes.add("pitchAxisMin", {
  type: "number",
  default: -80,
});
OrbitCameraControl.attributes.add("autoRotationColdown", {
  type: "number",
  default: 5000,
});
OrbitCameraControl.attributes.add("fixedPostionMoveCurve", {
  type: "curve",
});
OrbitCameraControl.attributes.add("fixedPostionRotationCanInterrupt", {
  type: "boolean",
});
OrbitCameraControl.attributes.add("setPauseEvent", {
  type: "string",
  default: "pauseCam:ext",
});
OrbitCameraControl.attributes.add("initPitch", {
  type: "number",
  default: 0,
});
OrbitCameraControl.attributes.add("initYaw", {
  type: "number",
  default: 0,
});
OrbitCameraControl.prototype.initialize = function () {
  this.enabled = this.entity.enabled;
  this.weight = 1;
  this.oldQuat = new pc.Quat();
  this.pitchS = -20;
  this.yawS = 10;
  this.app.mouse &&
    (this.app.mouse.on(pc.EVENT_MOUSEDOWN, this.onMouseDown, this),
    this.app.mouse.on(pc.EVENT_MOUSEMOVE, this.onMouseMove, this),
    this.app.mouse.on(pc.EVENT_MOUSEUP, this.onMouseUp, this),
    this.app.mouse.on(pc.EVENT_MOUSEWHEEL, this.onMouseWheel, this));
  this.app.touch &&
    (this.app.touch.on(pc.EVENT_TOUCHSTART, this.onTouchStart, this),
    this.app.touch.on(pc.EVENT_TOUCHMOVE, this.onTouchMove, this),
    this.app.touch.on(pc.EVENT_TOUCHCANCEL, this.onTouchEnd, this),
    this.app.touch.on(pc.EVENT_TOUCHEND, this.onTouchEnd, this));
  this.app.on(this.setPauseEvent, this.onSetPause, this);
  this.rotating = false;
  this.pitch = this.initPitch;
  this.yaw = this.initYaw;
  this.pitchTarget = this.pitch;
  this.yawTarget = this.yaw;
  this.m = {
    x: 0,
    y: 0,
  };
  this.ml = {
    x: 0,
    y: 0,
  };
  this.entity.setEulerAngles(this.pitch, this.yaw, 0);
  this.rotateEnd = Date.now();
  this.touchInd = -1;
  this.app.on("rotate_in_period", this.onRotateInPeriod, this);
  this.mode = 1;
  this.fixedPositionRotationTimeCount = 0;
  this.lastPinchDistance = 0;
  this.bPauseControl = false;
};
OrbitCameraControl.prototype.onSetPause = function (t) {
  this.bPauseControl = t;
};
OrbitCameraControl.prototype.onMouseDown = function (t) {
  this.bPauseControl ||
    ((2 != this.mode || this.fixedPostionRotationCanInterrupt) &&
      ((this.rotating = true),
      (this.m.x = t.x),
      (this.m.y = t.y),
      (this.ml.x = t.x),
      (this.ml.y = t.y),
      (this.mode = 1),
      (this.fixedPositionRotationTimeCount = 0)));
};
OrbitCameraControl.prototype.onRotateInPeriod = function (t, i, o) {
  this.fixedPositionRotationDuration = o;
  this.manualPitch = t;
  this.manualYaw = i;
  this.currentPitch = this.pitch;
  this.currentYaw = this.yaw;
  this.mode = 2;
  this.fixedPositionRotationTimeCount = 0;
};
OrbitCameraControl.prototype.onMouseMove = function (t) {
  this.bPauseControl || ((this.m.x = t.x), (this.m.y = t.y));
};
OrbitCameraControl.prototype.onMouseUp = function () {
  this.bPauseControl ||
    ((this.rotating = false), (this.rotateEnd = Date.now()));
};
OrbitCameraControl.prototype.onTouchStart = function (t) {
  if (
    !this.bPauseControl &&
    (2 != this.mode || this.fixedPostionRotationCanInterrupt) &&
    ((this.rotating = true),
    -1 === this.touchInd && t.touches.length && 1 === t.touches.length)
  ) {
    var i = t.touches[0];
    this.touchInd = i.identifier;
    this.m.x = i.x;
    this.m.y = i.y;
    this.ml.x = this.m.x;
    this.ml.y = this.m.y;
    this.mode = 1;
    this.fixedPositionRotationTimeCount = 0;
  }
};
OrbitCameraControl.prototype.getPinchDistance = function (t, i) {
  var o = t.x - i.x,
    s = t.y - i.y;
  return Math.sqrt(o * o + s * s);
};
OrbitCameraControl.prototype.onTouchMove = function (t) {
  if (!this.bPauseControl) {
    var i = t.touches;
    if (1 === i.length) {
      var o = i[0];
      this.m.x = o.x;
      this.m.y = o.y;
    } else i.length;
  }
};
OrbitCameraControl.prototype.onTouchEnd = function (t) {
  this.bPauseControl ||
    ((this.rotating = false),
    (this.rotateEnd = Date.now()),
    (this.touchInd = -1));
};
OrbitCameraControl.prototype.update = function (t) {
  if (this.enabled)
    switch (this.mode) {
      case 1:
        if (this.rotating) {
          var i = this.ml.x - this.m.x,
            o = this.ml.y - this.m.y;
          this.pitchTarget = Math.max(
            -this.pitchAxisMax,
            Math.min(this.pitchAxisMin, this.pitchTarget + o * this.sensivity),
          );
          this.yawTarget += i * this.sensivity;
          this.ml.x = this.m.x;
          this.ml.y = this.m.y;
        } else
          Date.now() - this.rotateEnd > this.autoRotationColdown &&
            (this.yawTarget +=
              10 *
              t *
              Math.min(1, (Date.now() - this.rotateEnd - 1000) / 2000));
        Math.abs(this.pitch - this.pitchTarget) +
          Math.abs(this.yaw - this.yawTarget) >
          0.1 &&
          ((this.pitch += (this.pitchTarget - this.pitch) * this.easing),
          (this.yaw += (this.yawTarget - this.yaw) * this.easing),
          this.oldQuat.copy(this.entity.getRotation()),
          this.entity.setEulerAngles(this.pitch, this.yaw, 0),
          this.oldQuat.slerp(
            this.oldQuat,
            this.entity.getRotation(),
            this.weight,
          ),
          this.entity.setRotation(this.oldQuat));
        break;
      case 2:
        this.fixedPositionRotationTimeCount += t;
        var s =
            this.currentPitch +
            this.manualPitch *
              this.fixedPostionMoveCurve.value(
                this.fixedPositionRotationTimeCount /
                  this.fixedPositionRotationDuration,
              ),
          e =
            this.currentYaw +
            this.manualYaw *
              this.fixedPostionMoveCurve.value(
                this.fixedPositionRotationTimeCount /
                  this.fixedPositionRotationDuration,
              );
        this.oldQuat.copy(this.entity.getRotation());
        this.entity.setEulerAngles(s, e, 0);
        this.oldQuat.slerp(
          this.oldQuat,
          this.entity.getRotation(),
          this.weight,
        );
        this.entity.setRotation(this.oldQuat);
        this.pitch = s;
        this.yaw = e;
        this.pitchTarget = this.pitch;
        this.yawTarget = this.yaw;
        this.fixedPositionRotationTimeCount >=
          this.fixedPositionRotationDuration &&
          ((this.rotateEnd = Date.now()),
          (this.mode = 1),
          (this.fixedPositionRotationTimeCount = 0));
    }
};
