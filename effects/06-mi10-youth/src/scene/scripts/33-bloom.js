/* Scene behavior: bloom. Registered in original execution order. */
var Bloom = pc.createScript("bloom");
Bloom.attributes.add("bloomIntensity", {
  type: "number",
  default: 1,
  min: 0,
  title: "Intensity",
});
Bloom.attributes.add("bloomThreshold", {
  type: "number",
  default: 0.25,
  min: 0,
  max: 1,
  precision: 2,
  title: "Threshold",
});
Bloom.attributes.add("blurAmount", {
  type: "number",
  default: 4,
  min: 1,
  title: "Blur amount",
});
Bloom.prototype.initialize = function () {
  this.effect = new pc.BloomEffect(this.app.graphicsDevice);
  this.effect.bloomThreshold = this.bloomThreshold;
  this.effect.blurAmount = this.blurAmount;
  this.effect.bloomIntensity = this.bloomIntensity;
  var e = this.entity.camera.postEffects;
  e.addEffect(this.effect);
  this.on(
    "attr",
    function (e, t) {
      this.effect[e] = t;
    },
    this,
  );
  this.on("state", function (t) {
    t ? e.addEffect(this.effect) : e.removeEffect(this.effect);
  });
  this.on("destroy", function () {
    e.removeEffect(this.effect);
  });
};
