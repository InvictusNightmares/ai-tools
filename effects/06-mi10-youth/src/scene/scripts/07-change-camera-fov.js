/* Scene behavior: change-camera-fov. Registered in original execution order. */
var ChangeCameraFov = pc.createScript("changeCameraFov");
ChangeCameraFov.attributes.add("VerticalFov", {
  type: "number",
  default: 30,
  title: "移动端竖屏fov",
});
ChangeCameraFov.attributes.add("HorizontalFov", {
  type: "number",
  default: 45,
  title: "移动端横屏fov",
});
ChangeCameraFov.prototype.initialize = function () {
  if (((this.Cam = this.entity.camera), this.Cam && !IsPC())) {
    this.app.graphicsDevice.width / this.app.graphicsDevice.height < 1 &&
      this.setVerticalFov();
    var t = this;
    window.addEventListener("resize", function () {
      t.app.graphicsDevice.width / t.app.graphicsDevice.height < 1
        ? t.setVerticalFov()
        : t.setHorizontalFov();
    });
  }
};
ChangeCameraFov.prototype.update = function (t) {};
ChangeCameraFov.prototype.setVerticalFov = function () {
  this.Cam.fov = this.VerticalFov;
};
ChangeCameraFov.prototype.setHorizontalFov = function () {
  this.Cam.fov = this.HorizontalFov;
};
