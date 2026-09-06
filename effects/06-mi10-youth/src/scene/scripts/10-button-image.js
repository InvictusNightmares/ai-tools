/* Scene behavior: button-image. Registered in original execution order. */
var ButtonImage = pc.createScript("buttonImage");
ButtonImage.attributes.add("buttons", {
  array: true,
  type: "entity",
});
ButtonImage.attributes.add("button_icon_actives", {
  array: true,
  type: "asset",
  assetType: "texture",
});
ButtonImage.attributes.add("button_icon_hovers", {
  array: true,
  type: "asset",
  assetType: "texture",
});
ButtonImage.prototype.initialize = function () {};
ButtonImage.prototype.update = function (t) {};
ButtonImage.prototype.SetButtonIcon = function (t) {
  for (i = 0; i < this.buttons.length; i++)
    i === t
      ? (this.buttons[i].element.textureAsset = this.button_icon_actives[i])
      : (this.buttons[i].element.textureAsset = this.button_icon_hovers[i]);
};
