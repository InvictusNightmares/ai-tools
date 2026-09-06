/* Scene behavior: controller-blast. Registered in original execution order. */
var ControllerBlast = pc.createScript("controllerBlast");
ControllerBlast.attributes.add("clickEvent", {
  type: "string",
  title: "点击事件",
});
ControllerBlast.attributes.add("buttonIndex", {
  type: "number",
  default: 0,
  title: "按钮Index",
});
ControllerBlast.attributes.add("phoneState", {
  type: "number",
  default: 0,
  title: "手机状态",
});
ControllerBlast.prototype.initialize = function () {
  this.entity.button.on("click", this._onClick, this);
  this.isClick = false;
  this.isCanClick = true;
};
ControllerBlast.prototype.update = function (t) {};
ControllerBlast.prototype._onClick = function (t) {
  this.fireEvent();
};
ControllerBlast.prototype.fireEvent = function () {
  this.isClick = !this.isClick;
  this.app.fire(this.clickEvent, this.isClick, this.phoneState);
  this.isClick
    ? this.app.fire("HiddenButtons", this.buttonIndex)
    : this.app.fire("ShowButtons");
};
