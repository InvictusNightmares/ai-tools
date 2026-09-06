/* Scene behavior: open-box. Registered in original execution order. */
var OpenBox = pc.createScript("openBox");
OpenBox.prototype.initialize = function () {
  this.entity.button.on("click", this._onClick, this);
};
OpenBox.prototype.update = function (o) {};
OpenBox.prototype._onClick = function (o) {
  this.app.fire("cam_openBox");
};
