/* Scene behavior: asset-manager. Registered in original execution order. */
var AssetManager = pc.createScript("assetManager");
AssetManager.attributes.add("unboxing_textures", {
  type: "asset",
  assetType: "texture",
  array: true,
});
AssetManager.attributes.add("camera_texutres", {
  type: "asset",
  assetType: "texture",
  array: true,
});
AssetManager.prototype.initialize = function () {
  this.app.on(
    "assetManager:unload_unboxing_textures",
    function () {
      this.app.fire(
        "assetsLoader:unload",
        this.unboxing_textures,
        true,
        function () {},
      );
    },
    this,
  );
  this.app.on(
    "assetManager:load_camera_textures",
    function () {
      this.app.fire(
        "assetsLoader:load",
        this.camera_texutres,
        true,
        function () {},
      );
    },
    this,
  );
};
AssetManager.prototype.update = function (t) {};
