/* Scene behavior: multiple-switch. Registered in original execution order. */
var MultipleSwitch = pc.createScript("multipleSwitch");
MultipleSwitch.prototype.initialize = function () {
  var t = this;
  this.entity.scrollbar.on("set:value", function () {
    t.app.fire(
      "phone:changeCameraScale",
      49.4 * t.entity.scrollbar.value + 0.6,
    );
  });
};
MultipleSwitch.prototype.update = function (t) {};
