/* Scene behavior: click-camera-hotspot-button. Registered in original execution order. */
var ClickCameraHotspotButton = pc.createScript("clickCameraHotspotButton");
ClickCameraHotspotButton.attributes.add("cameraIndex", {
  type: "number",
  default: 0,
  title: "点击相机的index",
});
ClickCameraHotspotButton.prototype.initialize = function () {
  this.entity.button.on("click", this._onClick, this);
};
ClickCameraHotspotButton.prototype.update = function (t) {};
ClickCameraHotspotButton.prototype._onClick = function () {
  this.app.fire("phone:hotspot_camera_detail", this.cameraIndex);
};
