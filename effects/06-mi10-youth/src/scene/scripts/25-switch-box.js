/* Scene behavior: switch-box. Registered in original execution order. */
var SwitchBox = pc.createScript("switchBox");
SwitchBox.attributes.add("boxIndex", {
  type: "number",
  default: 0,
});
SwitchBox.prototype.initialize = function () {
  this.entity.button.on("click", this._onClick, this);
};
SwitchBox.prototype.update = function (t) {};
SwitchBox.prototype._onClick = function (t) {
  this.app.fire("box:switchTexture", this.boxIndex);
};
