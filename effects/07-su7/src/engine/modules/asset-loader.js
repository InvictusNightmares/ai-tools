import { defineField as B } from "../fields.js";
// Recovered runtime module; preserve lazy initialization for cyclic dependencies.
export default (t, n, r) => {
  r.d(n, {
    g: () => s,
  });
  class s {
    constructor(l) {
      B(this, "viewer");
      B(this, "name", "");
      this.viewer = l;
    }
  }
};
