/* Scene behavior: hotspot. Registered in original execution order. */
var Hotspot = pc.createScript("hotspot");
Hotspot.attributes.add("cameraEntity", {
  type: "entity",
  title: "Camera Entity",
});
Hotspot.attributes.add("radius", {
  type: "number",
  title: "Radius",
});
Hotspot.attributes.add("event_index", {
  type: "number",
  title: "event index",
});
Hotspot.prototype.initialize = function () {
  this.hitArea = new pc.BoundingSphere(this.entity.getPosition(), this.radius);
  this.ray = new pc.Ray();
  this.sprite = this.entity.children[0];
  this.app.mouse
    ? (this.app.mouse.on(pc.EVENT_MOUSEDOWN, this.onMouseDown, this),
      this.app.mouse.on(pc.EVENT_MOUSEUP, this.onMouseUp, this))
    : (this.app.touch.on(pc.EVENT_TOUCHSTART, this.onTouchStart, this),
      this.app.touch.on(pc.EVENT_TOUCHEND, this.onTouchUp, this));
  this.isPressed = false;
  this.minIntensity = 0.8;
  this.maxIntensity = 1;
  this.currIntensity = 0.8;
  this.direction = "up";
};
Hotspot.prototype.update = function (t) {
  var i = this.cameraEntity.getPosition();
  this.entity.lookAt(i);
  this.sprite.setLocalScale(
    this.currIntensity,
    this.currIntensity,
    this.currIntensity,
  );
};
Hotspot.prototype.fireEvent = function () {
  this.app.fire("phone:hotspot_blast_detail", this.event_index, true);
};
Hotspot.prototype.doRayCast = function (t) {
  if (this.sprite.enabled)
    return (
      this.cameraEntity.camera.screenToWorld(
        t.x,
        t.y,
        this.cameraEntity.camera.farClip,
        this.ray.direction,
      ),
      this.ray.origin.copy(this.cameraEntity.getPosition()),
      this.ray.direction.sub(this.ray.origin).normalize(),
      this.hitArea.intersectsRay(this.ray)
    );
};
Hotspot.prototype.onMouseDown = function (t) {
  this.isPressed = this.doRayCast(t);
};
Hotspot.prototype.onMouseUp = function (t) {
  this.doRayCast(t) &&
    this.isPressed &&
    (this.fireEvent(), (this.isPressed = false));
};
Hotspot.prototype.onTouchUp = function (t) {
  1 == t.touches.length &&
    this.doRayCast(t.touches[0]) &&
    this.isPressed &&
    (this.fireEvent(), (this.isPressed = false));
};
Hotspot.prototype.onTouchStart = function (t) {
  this.isPressed = this.doRayCast(t.touches[0]);
};
