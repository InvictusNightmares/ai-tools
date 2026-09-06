/* Scene behavior: fps. Registered in original execution order. */
var Fps = pc.createScript("fps");
Fps.prototype.initialize = function () {
  this.fps = new FPSMeter({
    heat: true,
    graph: true,
  });
};
Fps.prototype.update = function (t) {
  this.fps.tick();
  this.app.fire("update_fps", this.fps.fps);
};
