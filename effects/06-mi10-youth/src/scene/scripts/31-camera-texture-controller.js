/* Scene behavior: camera-texture-controller. Registered in original execution order. */
var CameraTextureController = pc.createScript("cameraTextureController");
CameraTextureController.attributes.add("scrollbarEntity", {
  type: "entity",
});
CameraTextureController.attributes.add("textureMaterial", {
  type: "asset",
  assetType: "material",
});
CameraTextureController.attributes.add("cameraTextures", {
  type: "asset",
  assetType: "texture",
  array: true,
});
CameraTextureController.prototype.initialize = function () {
  this.mapOffset = new pc.Vec2(0, 0);
  this.MapTiling = new pc.Vec2(1, 1);
  this.beginOffset = this.mapOffset;
  this.beginTiling = this.MapTiling;
  this.currentCameraState = 0;
  this.oldCameraState = 0;
  this.app.on("phone:changeCameraScale", this.changeCameraScale, this);
};
CameraTextureController.prototype.postInitialize = function () {
  this.app.fire("assetManager:load_camera_textures");
};
CameraTextureController.prototype.changeCameraScale = function (t) {
  var e = (t - 0.6) / 49.4,
    a = 1;
  e <= 0.02 && ((this.currentCameraState = 0), (a = 1 - 13 * e));
  e > 0.02 &&
    e <= 0.045 &&
    ((this.currentCameraState = 1), (a = 1 - 7.4 * (e - 0.02)));
  e > 0.045 &&
    e <= 0.08 &&
    ((this.currentCameraState = 2), (a = 1 - 8.5 * (e - 0.05)));
  e > 0.08 &&
    e <= 0.11 &&
    ((this.currentCameraState = 3), (a = 1 - 7 * (e - 0.08)));
  e > 0.11 &&
    e <= 0.14 &&
    ((this.currentCameraState = 4), (a = 1 - 8 * (e - 0.11)));
  e > 0.14 &&
    e <= 0.17 &&
    ((this.currentCameraState = 5), (a = 1 - 7 * (e - 0.14)));
  e > 0.17 &&
    e <= 0.2 &&
    ((this.currentCameraState = 6), (a = 1 - 8 * (e - 0.17)));
  e > 0.2 &&
    e <= 0.23 &&
    ((this.currentCameraState = 7), (a = 1 - 7.5 * (e - 0.2)));
  e > 0.23 &&
    e <= 0.27 &&
    ((this.currentCameraState = 8), (a = 1 - 6 * (e - 0.23)));
  e > 0.27 &&
    e <= 0.3 &&
    ((this.currentCameraState = 9), (a = 1 - 8 * (e - 0.27)));
  e > 0.3 &&
    e <= 0.35 &&
    ((this.currentCameraState = 10), (a = 1 - 4 * (e - 0.3)));
  e > 0.35 &&
    e <= 0.425 &&
    ((this.currentCameraState = 11), (a = 1 - 3.2 * (e - 0.35)));
  e > 0.425 &&
    e <= 0.5 &&
    ((this.currentCameraState = 12), (a = 1 - 3.3 * (e - 0.425)));
  e > 0.5 &&
    e <= 0.6 &&
    ((this.currentCameraState = 13), (a = 1 - 1.72 * (e - 0.5)));
  e > 0.6 &&
    e <= 0.725 &&
    ((this.currentCameraState = 14), (a = 1 - 1.65 * (e - 0.6)));
  e > 0.725 &&
    e <= 0.85 &&
    ((this.currentCameraState = 15), (a = 1 - 2 * (e - 0.725)));
  e > 0.85 &&
    e <= 1 &&
    ((this.currentCameraState = 16), (a = 1 - 0.4 * (e - 0.85)));
  a = pc.math.clamp(a, 0.1, 1);
  this.oldCameraState != this.currentCameraState &&
    ((this.textureMaterial.resource.emissiveMap =
      this.cameraTextures[this.currentCameraState].resource),
    (this.oldCameraState = this.currentCameraState));
  this.MapTiling.x = a;
  this.MapTiling.y = a;
  this.mapOffset.x = -0.5 * (a - 1);
  this.mapOffset.y = -0.5 * (a - 1);
  this.textureMaterial.resource.emissiveMapTiling = this.MapTiling;
  this.textureMaterial.resource.emissiveMapOffset = this.mapOffset;
  this.textureMaterial.resource.update();
};
CameraTextureController.prototype.update = function (t) {};
