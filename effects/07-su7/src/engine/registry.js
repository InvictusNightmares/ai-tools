import module879 from "./modules/camera-brain.js";
import module585 from "./modules/free-camera.js";
import module313 from "./modules/virtual-camera.js";
import module461 from "./modules/entity.js";
import module128 from "./modules/orientation.js";
import module930 from "./modules/event-emitter.js";
import module779 from "./modules/scheduler.js";
import module861 from "./modules/math-helpers.js";
import module591 from "./modules/component.js";
import module41 from "./modules/properties.js";
import module694 from "./modules/input.js";
import module322 from "./modules/render-context.js";
import module282 from "./modules/cache.js";
import module811 from "./modules/preload.js";
import module822 from "./modules/viewer.js";
import module25 from "./modules/three-exports.js";
import module481 from "./modules/tween-manager.js";
import module400 from "./modules/components.js";
import module745 from "./modules/asset-loader.js";
import module353 from "./modules/loaders.js";
import module741 from "./modules/material.js";
import module678 from "./modules/image-loader.js";
import module28 from "./modules/screen.js";
import module616 from "./modules/image-data.js";
import module465 from "./modules/browser.js";
import module876 from "./modules/noise.js";
import module459 from "./modules/utils.js";
import module992 from "./modules/plugin.js";
import module893 from "./modules/camera-plugin.js";
import module427 from "./modules/url-utils.js";
import module371 from "./modules/render-utils.js";
import module774 from "./modules/mesh-utils.js";
import module150 from "./modules/transform-controls.js";
import module477 from "./modules/three-r150.js";
import module980 from "./modules/file-utils.js";
import module631 from "./modules/tween-chain.js";
import module622 from "./modules/tween.js";
const modules = {
  879: module879,
  585: module585,
  313: module313,
  461: module461,
  128: module128,
  930: module930,
  779: module779,
  861: module861,
  591: module591,
  41: module41,
  694: module694,
  322: module322,
  282: module282,
  811: module811,
  822: module822,
  25: module25,
  481: module481,
  400: module400,
  745: module745,
  353: module353,
  741: module741,
  678: module678,
  28: module28,
  616: module616,
  465: module465,
  876: module876,
  459: module459,
  992: module992,
  893: module893,
  427: module427,
  371: module371,
  774: module774,
  150: module150,
  477: module477,
  980: module980,
  631: module631,
  622: module622,
};
const cache = {};
export function requireModule(id) {
  if (cache[id]) return cache[id].exports;
  const module = (cache[id] = { exports: {} });
  modules[id](module, module.exports, requireModule);
  return module.exports;
}
requireModule.d = (target, getters) => {
  for (const key in getters)
    if (!Object.prototype.hasOwnProperty.call(target, key))
      Object.defineProperty(target, key, { enumerable: true, get: getters[key] });
};
requireModule.o = (obj, key) => Object.prototype.hasOwnProperty.call(obj, key);
requireModule.r = (target) => {
  Object.defineProperty(target, Symbol.toStringTag, { value: "Module" });
  Object.defineProperty(target, "__esModule", { value: true });
};
