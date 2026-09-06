/* Scene behavior: mouse-input. Registered in original execution order. */
var MouseInput = pc.createScript("mouseInput");
MouseInput.attributes.add("orbitSensitivity", {
  type: "number",
  default: 0.3,
  title: "Orbit Sensitivity",
  description: "How fast the camera moves around the orbit. Higher is faster",
});
MouseInput.attributes.add("distanceSensitivity", {
  type: "number",
  default: 0.15,
  title: "Distance Sensitivity",
  description: "How fast the camera moves in and out. Higher is faster",
});
MouseInput.prototype.initialize = function () {
  if (((this.orbitCamera = this.entity.script.orbitCamera), this.orbitCamera)) {
    var t = this,
      o = function (o) {
        t.onMouseOut(o);
      };
    this.app.mouse.on(pc.EVENT_MOUSEDOWN, this.onMouseDown, this);
    this.app.mouse.on(pc.EVENT_MOUSEUP, this.onMouseUp, this);
    this.app.mouse.on(pc.EVENT_MOUSEMOVE, this.onMouseMove, this);
    this.app.mouse.on(pc.EVENT_MOUSEWHEEL, this.onMouseWheel, this);
    window.addEventListener("mouseout", o, false);
    this.on("destroy", function () {
      this.app.mouse.off(pc.EVENT_MOUSEDOWN, this.onMouseDown, this);
      this.app.mouse.off(pc.EVENT_MOUSEUP, this.onMouseUp, this);
      this.app.mouse.off(pc.EVENT_MOUSEMOVE, this.onMouseMove, this);
      this.app.mouse.off(pc.EVENT_MOUSEWHEEL, this.onMouseWheel, this);
      window.removeEventListener("mouseout", o, false);
    });
  }
  this.app.mouse.disableContextMenu();
  this.lookButtonDown = false;
  this.panButtonDown = false;
  this.lastPoint = new pc.Vec2();
};
MouseInput.fromWorldPoint = new pc.Vec3();
MouseInput.toWorldPoint = new pc.Vec3();
MouseInput.worldDiff = new pc.Vec3();
MouseInput.prototype.pan = function (t) {
  var o = MouseInput.fromWorldPoint,
    e = MouseInput.toWorldPoint,
    i = MouseInput.worldDiff,
    s = this.entity.camera,
    n = this.orbitCamera.distance;
  s.screenToWorld(t.x, t.y, n, o);
  s.screenToWorld(this.lastPoint.x, this.lastPoint.y, n, e);
  i.sub2(e, o);
  this.orbitCamera.pivotPoint.add(i);
};
MouseInput.prototype.onMouseDown = function (t) {
  switch (t.button) {
    case pc.MOUSEBUTTON_LEFT:
      this.lookButtonDown = true;
      break;
    case pc.MOUSEBUTTON_MIDDLE:
    case pc.MOUSEBUTTON_RIGHT:
      this.panButtonDown = true;
  }
};
MouseInput.prototype.onMouseUp = function (t) {
  switch (t.button) {
    case pc.MOUSEBUTTON_LEFT:
      this.lookButtonDown = false;
      break;
    case pc.MOUSEBUTTON_MIDDLE:
    case pc.MOUSEBUTTON_RIGHT:
      this.panButtonDown = false;
  }
};
MouseInput.prototype.onMouseMove = function (t) {
  if (toogleCameraRotate) {
    pc.app.mouse;
    this.lookButtonDown
      ? (toogleCameraPitch &&
          (this.orbitCamera.pitch -= t.dy * this.orbitSensitivity),
        (this.orbitCamera.yaw -= t.dx * this.orbitSensitivity))
      : this.panButtonDown && this.orbitCamera.panning && this.pan(t);
    this.lastPoint.set(t.x, t.y);
  }
};
MouseInput.prototype.onMouseWheel = function (t) {
  toogleCameraRotate &&
    ((this.orbitCamera.distance -=
      t.wheel * this.distanceSensitivity * (0.1 * this.orbitCamera.distance)),
    t.event.preventDefault());
};
MouseInput.prototype.onMouseOut = function (t) {
  this.lookButtonDown = false;
  this.panButtonDown = false;
};
