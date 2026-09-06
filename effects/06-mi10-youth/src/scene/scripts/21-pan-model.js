/* Scene behavior: pan-model. Registered in original execution order. */
var PanModel = pc.createScript("panModel");
PanModel.attributes.add("mainCamera", {
  type: "entity",
  title: "相机",
});
PanModel.attributes.add("phone", {
  type: "entity",
  title: "手机",
});
PanModel.prototype.initialize = function () {
  this.panButtonDown = false;
  this.lastPoint = new pc.Vec2();
  this.lastTouchPoint = new pc.Vec2();
  this.lastPinchMidPoint = new pc.Vec2();
  IsPC()
    ? this.app.mouse &&
      (this.app.mouse.on(pc.EVENT_MOUSEDOWN, this.onMouseDown, this),
      this.app.mouse.on(pc.EVENT_MOUSEUP, this.onMouseUp, this),
      this.app.mouse.on(pc.EVENT_MOUSEMOVE, this.onMouseMove, this),
      window.addEventListener("mouseout", this.onMouseOut, false),
      this.on("destroy", function () {
        this.app.mouse.off(pc.EVENT_MOUSEDOWN, this.onMouseDown, this);
        this.app.mouse.off(pc.EVENT_MOUSEUP, this.onMouseUp, this);
        this.app.mouse.off(pc.EVENT_MOUSEMOVE, this.onMouseMove, this);
        window.removeEventListener("mouseout", onMouseOut, false);
      }))
    : this.app.touch &&
      (this.app.touch.on(pc.EVENT_TOUCHSTART, this.onTouchStartEndCancel, this),
      this.app.touch.on(pc.EVENT_TOUCHEND, this.onTouchStartEndCancel, this),
      this.app.touch.off(
        pc.EVENT_TOUCHCANCEL,
        this.onTouchStartEndCancel,
        this,
      ),
      this.app.touch.on(pc.EVENT_TOUCHMOVE, this.onTouchMove, this),
      this.on("destroy", function () {
        this.app.touch.off(
          pc.EVENT_TOUCHSTART,
          this.onTouchStartEndCancel,
          this,
        );
        this.app.touch.off(pc.EVENT_TOUCHEND, this.onTouchStartEndCancel, this);
        this.app.touch.off(
          pc.EVENT_TOUCHCANCEL,
          this.onTouchStartEndCancel,
          this,
        );
        this.app.touch.off(pc.EVENT_TOUCHMOVE, this.onTouchMove, this);
      }));
  var t = this;
  this.panToggle = false;
  this.app.on(
    "controllerPanToggle",
    (this.setPanToggle = function (o) {
      t.panToggle = o;
    }),
  );
};
PanModel.prototype.update = function (t) {};
PanModel.prototype.onMouseDown = function (t) {
  switch (t.button) {
    case pc.MOUSEBUTTON_LEFT:
      break;
    case pc.MOUSEBUTTON_RIGHT:
      this.panButtonDown = true;
  }
};
PanModel.prototype.onMouseUp = function (t) {
  switch (t.button) {
    case pc.MOUSEBUTTON_LEFT:
      break;
    case pc.MOUSEBUTTON_RIGHT:
      this.panButtonDown = false;
  }
};
PanModel.prototype.onMouseMove = function (t) {
  false !== this.panToggle &&
    (true === this.panButtonDown && this.pan(t), this.lastPoint.set(t.x, t.y));
};
PanModel.prototype.onMouseOut = function (t) {
  this.panButtonDown = false;
};
PanModel.prototype.onTouchStartEndCancel = function (t) {
  if (false !== this.panToggle) {
    toogleCameraRotate = true;
    this.isXMove = false;
    this.isYMove = false;
    var o = t.touches;
    1 == o.length
      ? (this.lastTouchPoint.set(o[0].x, o[0].y),
        this.calcMidPoint(o[0], o[0], this.lastPinchMidPoint))
      : o.length;
  }
};
PanModel.prototype.calcMidPoint = function (t, o, n) {
  n.set(t.x, t.y);
  n.scale(0.5);
  n.x += t.x / 5;
  n.y += t.y / 5;
};
PanModel.pinchMidPoint = new pc.Vec2();
PanModel.moveTouchPoint = new pc.Vec2();
PanModel.prototype.onTouchMove = function (t) {
  if (false !== this.panToggle) {
    var o = PanModel.pinchMidPoint,
      n = t.touches;
    if (1 == n.length) {
      var i = PanModel.moveTouchPoint;
      i.set(n[0].x, n[0].y);
      var e = Math.abs(i.x - this.lastTouchPoint.x);
      if (Math.abs(i.y - this.lastTouchPoint.y) >= e) {
        if (this.isXMove) return;
        this.isYMove = true;
        toogleCameraRotate = false;
        this.calcMidPoint(n[0], n[0], o);
        this.pan(o);
        this.lastPinchMidPoint.copy(o);
      } else {
        if (this.isYMove) return;
        this.isXMove = true;
      }
    } else n.length;
  }
};
PanModel.fromWorldPoint = new pc.Vec3();
PanModel.toWorldPoint = new pc.Vec3();
PanModel.worldDiff = new pc.Vec3();
PanModel.beginScreenPoint = new pc.Vec2();
PanModel.prototype.pan = function (t) {
  var o = PanModel.fromWorldPoint,
    n = PanModel.toWorldPoint,
    i = PanModel.worldDiff,
    e = this.mainCamera.camera;
  e.screenToWorld(t.x, t.y, 10, o);
  IsPC()
    ? this.app.mouse &&
      e.screenToWorld(this.lastPoint.x, this.lastPoint.y, 10, n)
    : this.app.touch &&
      e.screenToWorld(
        this.lastPinchMidPoint.x,
        this.lastPinchMidPoint.y,
        10,
        n,
      );
  i.sub2(n, o);
  var s,
    a = new pc.Vec3();
  a = this.phone.getLocalPosition().clone();
  s = pc.math.clamp(a.y - i.y, -1, 1);
  this.phone.setLocalPosition(a.x, s, a.z);
};
