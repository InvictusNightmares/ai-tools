import { defineField as B } from "../fields.js";
// Recovered runtime module; preserve lazy initialization for cyclic dependencies.
export default (t, n, r) => {
  r.d(n, {
    LX: () => s,
    Vu: () => h,
    hR: () => l,
  });
  async function s(g) {
    return new Promise((_, A) => {
      const m = new FileReader();
      ((m.onload = () => _(m.result)), (m.onerror = A), m.readAsArrayBuffer(g));
    });
  }
  async function h(g) {
    return new Promise((_, A) => {
      const m = new FileReader();
      ((m.onload = () => _(m.result)), (m.onerror = A), m.readAsText(g));
    });
  }
  async function l(g) {
    return new Promise((_, A) => {
      const m = new FileReader();
      ((m.onload = () => _(m.result)), (m.onerror = A), m.readAsDataURL(g));
    });
  }
};
