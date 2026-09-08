import { defineField as B } from "../fields.js";
// Recovered runtime module; preserve lazy initialization for cyclic dependencies.
export default (t, n, r) => {
  r.d(n, {
    X: () => s,
  });
  class s {
    constructor(l, g, _) {
      B(this, "texture");
      B(this, "texCoords");
      B(this, "meshCoords");
      ((this.texture = l), (this.texCoords = g), (this.meshCoords = _));
    }
  }
};
