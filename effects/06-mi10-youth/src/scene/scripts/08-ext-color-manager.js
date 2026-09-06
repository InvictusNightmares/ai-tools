/* Scene behavior: ext-color-manager. Registered in original execution order. */
var ExtColorManager = pc.createScript("extColorManager");
ExtColorManager.attributes.add("ext_index", {
  type: "number",
  title: "默认颜色",
  default: 0,
  enum: [
    {
      白: 0,
    },
    {
      绿: 1,
    },
    {
      橙金: 2,
    },
    {
      蓝黑: 3,
    },
    {
      黑: 4,
    },
  ],
});
ExtColorManager.prototype.initialize = function () {
  this.app.on(
    "exterior:change_color",
    this.onExtChangeColorEventPreHandler,
    this,
  );
  this.onExtChangeColorEventPreHandler(this.ext_index);
};
ExtColorManager.prototype.update = function (e) {};
ExtColorManager.prototype.onExtChangeColorEventPreHandler = function (e) {
  this.app.fire("material:change", 0, 4 * e);
  this.app.fire("material:change", 1, 4 * e + 1);
  this.app.fire("material:change", 2, 4 * e + 2);
  this.app.fire("material:change", 3, 4 * e + 3);
  this.app.fire("save:currentColorIndex", e);
};
ExtColorManager.prototype.swap = function (e) {};
