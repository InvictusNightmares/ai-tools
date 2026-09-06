/* Scene behavior: breath-light. Registered in original execution order. */
var BreathLight = pc.createScript("breathLight");
BreathLight.prototype.initialize = function () {
  this.totalTime = 0;
};
BreathLight.prototype.update = function (t) {
  this.target_mat = this.entity.model.meshInstances[2].material;
  this.totalTime += 1.25 * t;
  var i = 0.5 * (Math.sin(this.totalTime) + 1);
  this.target_mat.emissiveIntensity = i;
  this.target_mat.update();
};
