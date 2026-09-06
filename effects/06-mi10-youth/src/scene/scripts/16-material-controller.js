/* Scene behavior: material-controller. Registered in original execution order. */
var MaterialController = pc.createScript("materialController");
MaterialController.attributes.add("materialsToReplaced", {
  type: "asset",
  assetType: "material",
  array: true,
});
MaterialController.attributes.add("materialList", {
  type: "asset",
  assetType: "material",
  array: true,
});
MaterialController.attributes.add("triggerEvent", {
  type: "string",
  title: "Trigger Event",
  description: "2 params: old mat index, new mat index",
});
MaterialController.prototype.initialize = function () {
  this.app.on(this.triggerEvent, this.replaceMaterial, this);
  this.cloneList();
};
MaterialController.prototype.cloneList = function () {
  this.dict = [];
  var t = this,
    e = 0;
  this.app.root.find(function (a) {
    if (a.model) {
      var i = a.model.meshInstances;
      if (!i) return;
      for (var r = 0; r < i.length; ++r)
        for (var s = i[r], l = 0; l < t.materialsToReplaced.length; l++) {
          var o = s.material.id;
          o === t.materialsToReplaced[l].resource.id &&
            t.dict.push({
              mesh: s,
              id: o,
              uid: e++,
            });
        }
    }
  });
};
MaterialController.prototype.replaceMaterial = function (t, e) {
  if (
    this.materialsToReplaced[t] &&
    this.materialList[e] &&
    this.materialsToReplaced[t].resource != this.materialList[e].resource
  ) {
    this.oldMat = this.materialsToReplaced[t].resource;
    this.newMat = this.materialList[e].resource;
    this.meshesToReplaced = [];
    for (var a = 0; a < this.dict.length; a++) {
      this.dict[a].id === this.materialsToReplaced[t].resource.id &&
        ((this.dict[a].mesh.material = this.newMat),
        (this.dict[a].id = this.newMat.id));
    }
    this.materialsToReplaced[t] = this.materialList[e];
  }
};
MaterialController.prototype.update = function (t) {};
