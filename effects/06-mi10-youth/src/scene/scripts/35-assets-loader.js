/* Scene behavior: assets-loader. Registered in original execution order. */
var AssetsLoader = pc.createScript("assetsLoader");
AssetsLoader.attributes.add("max_reload", {
  type: "number",
  title: "最大重载次数",
});
AssetsLoader.prototype.initialize = function () {
  this.app.on("assetsLoader:load", this.startLoad, this);
  this.app.on("assetsLoader:unload", this.unload, this);
  this.reloadTimes = 0;
  this.assetsLeft = 0;
};
AssetsLoader.prototype.unload = function (s, e, t) {
  for (var o = 0; o < s.length; o++) {
    var a = s[o];
    if (!a) {
      console.error("unknown resource");
      break;
    }
    a.resource && a.unload();
    !e && t && t();
  }
  e && t && t();
};
AssetsLoader.prototype.startLoad = function (s, e, t) {
  this.assetsLeft > 0
    ? console.error("loading other assets now")
    : 0 !== s.length
      ? ((this.bLock = e),
        (this.succ_callback = t),
        (this.assetsLeft = s.length),
        this.loadAsset(s))
      : t && t();
};
AssetsLoader.prototype.loadAsset = function (s) {
  for (var e = 0; e < s.length; e++) {
    var t = s[e];
    if (!t) {
      console.error("unknown resrouce");
      break;
    }
    t.resource
      ? this.onAssetLoaded(t)
      : (t.once("load", this.onAssetLoaded, this),
        t.once("error", this.onAssetsLoaderr, this),
        this.app.assets.load(t));
  }
};
AssetsLoader.prototype.onAssetLoaded = function (s) {
  this.assetsLeft--;
  this.bLock
    ? 0 === this.assetsLeft && this.succ_callback(s)
    : this.succ_callback(s);
};
AssetsLoader.prototype.onAssetsLoaderr = function (s, e) {
  if ((this.reloadTimes++, this.reloadTimes === this.max_reload_times))
    return (
      console.error("max tries, load fail: " + e.name),
      void this.app.fire("assetsLoader:fail")
    );
  this.loadAsset(e);
};
