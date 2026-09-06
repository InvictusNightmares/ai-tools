/* Scene behavior: controller-cm. Registered in original execution order. */
var ControllerCm = pc.createScript("controllerCm");
ControllerCm.attributes.add("clickEvent", {
  type: "string",
  title: "点击事件",
});
ControllerCm.attributes.add("phoneState", {
  type: "number",
  default: 3,
  title: "手机状态",
});
ControllerCm.prototype.initialize = function () {
  this.entity.button.on("click", this._onClick, this);
  this.isClick = false;
};
ControllerCm.prototype.update = function (t) {};
ControllerCm.prototype._onClick = function () {
  var t = this;
  this.isClick = !this.isClick;
  this.app.fire(this.clickEvent, this.isClick, this.phoneState);
  this.isClick &&
    (this.app.fire("HiddenButtons", 5),
    setTimeout(function () {
      t.isClick = false;
      t.app.fire("ShowButtons");
    }, 4500));
};
