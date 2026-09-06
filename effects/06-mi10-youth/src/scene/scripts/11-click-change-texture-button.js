/* Scene behavior: click-change-texture-button. Registered in original execution order. */
var ClickChangeTextureButton = pc.createScript("clickChangeTextureButton");
ClickChangeTextureButton.attributes.add("selectNum", {
  type: "number",
  default: 0,
});
ClickChangeTextureButton.attributes.add("clickEventName", {
  type: "string",
  default: "exterior:change_color",
});
ClickChangeTextureButton.prototype.initialize = function () {
  this.app.mouse
    ? this.entity.element.on("mousedown", this.onPress, this)
    : this.entity.element.on("touchstart", this.onTouchStar, this);
};
ClickChangeTextureButton.prototype.update = function (t) {};
ClickChangeTextureButton.prototype.onPress = function (t) {
  this.fierNum();
};
ClickChangeTextureButton.prototype.onTouchStar = function (t) {
  1 === t.touches.length && this.fierNum();
};
ClickChangeTextureButton.prototype.fierNum = function () {
  var t = this.selectNum;
  this.app.fire(this.clickEventName, t);
  this.app.fire("changeButtonImage", t);
};
