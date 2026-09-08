import { defineField as B } from "../fields.js";
// Recovered runtime module; preserve lazy initialization for cyclic dependencies.
export default (t, n, r) => {
  r.d(n, {
    i: () => g,
  });
  var s = r(25),
    h;
  (function (A) {
    ((A[(A.NONE = 1)] = "NONE"), (A[(A.SELECTED = 2)] = "SELECTED"), (A[(A.IN = 4)] = "IN"));
  })(h || (h = {}));
  class l {
    constructor() {
      B(this, "_raycaster", new s.iMs());
      B(this, "_connectors", []);
    }
    connect(m) {
      let D = this._connectors.find((U) => U.target === m);
      D === void 0 &&
        ((D = {
          target: m,
          state: h.NONE,
        }),
        this._connectors.push(D));
    }
    disconnect(m) {
      let D = this._connectors.findIndex((U) => U.target === m);
      D !== -1 && this._connectors.splice(D, 1);
    }
    pointerDown(m, D) {
      if (this._connectors.length !== 0) {
        this._raycaster.setFromCamera(m, D);
        for (let U of this._connectors)
          if (U.target.has("click") || U.target.has("pointerdown")) {
            let R = this._raycaster.intersectObject(U.target.node, !0);
            R.length &&
              ((U.state |= h.SELECTED),
              U.target.emit("pointerdown", {
                intersects: R,
              }));
          }
      }
    }
    pointerUp(m, D) {
      if (this._connectors.length !== 0) {
        this._raycaster.setFromCamera(m, D);
        for (let U of this._connectors)
          if (U.target.has("click") || U.target.has("pointerup")) {
            let R = this._raycaster.intersectObject(U.target.node, !0);
            R.length &&
              (U.state & h.SELECTED &&
                ((U.state &= ~h.SELECTED),
                U.target.emit("click", {
                  intersects: R,
                })),
              U.target.emit("pointerup", {
                intersects: R,
              }));
          }
      }
    }
    pointerMove(m, D) {
      if (this._connectors.length !== 0) {
        this._raycaster.setFromCamera(m, D);
        for (let U of this._connectors)
          if (U.target.has("pointerover") || U.target.has("pointerout")) {
            let R = this._raycaster.intersectObject(U.target.node, !0);
            R.length
              ? U.state & h.IN ||
                ((U.state |= h.IN),
                U.target.emit("pointerover", {
                  intersects: R,
                }))
              : U.state & h.IN &&
                ((U.state &= ~h.IN),
                U.target.emit("pointerout", {
                  intersects: R,
                }));
          }
      }
    }
  }
  const _ = class _ {
    constructor(m) {
      B(this, "viewer");
      B(this, "_listeners", []);
      B(this, "_mouseWheel", 0);
      B(this, "_touches", []);
      B(this, "_touchCount", 0);
      B(this, "_pointerButton", -1);
      B(this, "_pointerPosition", new s.FM8());
      B(this, "_pointer", new s.FM8());
      B(this, "_keys", {});
      B(this, "_pressability", new l());
      this.viewer = m;
    }
    get pointerButton() {
      return this._pointerButton;
    }
    get pointer() {
      return this._pointer;
    }
    get pointerPosition() {
      return this._pointerPosition;
    }
    get mouseWheel() {
      return this._mouseWheel;
    }
    get touchCount() {
      return this._touchCount;
    }
    get touches() {
      return this._touches;
    }
    get keys() {
      return this._keys;
    }
    addEventListeners() {
      const m = this.viewer.renderer.domElement;
      ((m.style.touchAction = "none"),
        this._addEventListener(m, "contextmenu", (D) => D.preventDefault()),
        this._addEventListener(m, "pointerdown", (D) => this._onPointerDown(D), {
          passive: !1,
        }),
        this._addEventListener(m, "pointerup", (D) => this._onPointerUp(D), {
          passive: !1,
        }),
        this._addEventListener(m, "pointercancel", (D) => this._onPointerUp(D), {
          passive: !1,
        }),
        this._addEventListener(m, "pointerout", (D) => this._onPointerUp(D), {
          passive: !1,
        }),
        this._addEventListener(m, "pointermove", (D) => this._onPointerMove(D), {
          passive: !0,
        }),
        this._addEventListener(m, "wheel", (D) => this._onMouseWheel(D), {
          passive: !1,
        }),
        this._addEventListener(m, "touchstart", (D) => this._onTouchStart(D), {
          passive: !0,
        }),
        this._addEventListener(m, "touchend", (D) => this._onTouchEnd(D), {
          passive: !0,
        }),
        this._addEventListener(m, "touchmove", (D) => this._onTouchMove(D), {
          passive: !0,
        }),
        this._addEventListener(window, "keydown", (D) => this._onKeyDown(D), {
          passive: !1,
        }),
        this._addEventListener(window, "keypress", (D) => this._onKeyPress(D), {
          passive: !1,
        }),
        this._addEventListener(window, "keyup", (D) => this._onKeyUp(D), {
          passive: !1,
        }));
    }
    connect(m, D) {
      switch (D) {
        case _.CLICK:
        case _.POINTER_DOWN:
        case _.POINTER_UP:
        case _.POINTER_OVER:
        case _.POINTER_OUT:
          this._pressability.connect(m);
          break;
      }
    }
    disconnect(m) {
      this._pressability.disconnect(m);
    }
    _addEventListener(m, D, U, R) {
      (m.addEventListener ? m.addEventListener(D, U, R) : m.on && m.on(D, U, m),
        this._listeners.push({
          target: m,
          type: D,
          callback: U,
        }));
    }
    removeAllListeners() {
      for (let { target: m, type: D, callback: U } of this._listeners)
        m.removeEventListener ? m.removeEventListener(D, U) : m.off && m.off(D, U, m);
      this._listeners = [];
    }
    _remapPointer(m) {
      const D = this.viewer.width;
      return this.viewer.rootRotated
        ? {
            button: m.button,
            buttons: m.buttons,
            clientX: m.clientY,
            clientY: D - m.clientX,
            offsetX: m.offsetY,
            offsetY: D - m.offsetX,
            pageX: m.pageY,
            pageY: D - m.pageX,
            screenX: m.screenY,
            screenY: D - m.screenX,
            movementX: m.movementY,
            movementY: m.movementX,
          }
        : m;
    }
    _remapTouch(m) {
      const D = this.viewer.width;
      return this.viewer.rootRotated
        ? {
            touches: Array.from(m.touches).map((U) => ({
              identifier: U.identifier,
              clientX: U.clientY,
              clientY: D - U.clientX,
              pageX: U.pageY,
              pageY: D - U.pageX,
              screenX: U.screenY,
              screenY: D - U.screenX,
            })),
          }
        : m;
    }
    _computePointer(m) {
      ((this._pointer.x = (m.offsetX / this.viewer.width) * 2 - 1),
        (this._pointer.y = 1 - (m.offsetY / this.viewer.height) * 2),
        this._pointerPosition.set(m.offsetX, m.offsetY));
    }
    _onPointerDown(m) {
      (m.preventDefault(),
        (m = this._remapPointer(m)),
        (this._pointerButton = m.button),
        this._computePointer(m),
        this._pressability.pointerDown(this._pointer, this.viewer.camera),
        this.viewer.emit(_.POINTER_DOWN, m));
    }
    _onPointerUp(m) {
      (m.preventDefault(),
        (m = this._remapPointer(m)),
        (this._pointerButton = -1),
        this._computePointer(m),
        this._pressability.pointerUp(this._pointer, this.viewer.camera),
        this.viewer.emit(_.POINTER_UP, m));
    }
    _onPointerMove(m) {
      ((m = this._remapPointer(m)),
        this._computePointer(m),
        this._pressability.pointerMove(this._pointer, this.viewer.camera),
        this.viewer.emit(_.POINTER_MOVE, m));
    }
    _onMouseWheel(m) {
      (m.preventDefault(),
        (this._mouseWheel = m.deltaY || m.wheelDelta),
        this.viewer.emit(_.MOUSE_WHEEL, m));
    }
    _onTouchStart(m) {
      ((m = this._remapTouch(m)), this.viewer.emit(_.TOUCH_START, m));
    }
    _onTouchEnd(m) {
      ((m = this._remapTouch(m)), this.viewer.emit(_.TOUCH_END, m));
    }
    _onTouchMove(m) {
      m = this._remapTouch(m);
      let D = m.touches,
        U = this._touches;
      for (let R = D.length; R--;) {
        U[R] == null &&
          (U[R] = {
            id: -1,
            position: new s.FM8(),
          });
        const ne = D[R];
        ((U[R].id = ne.identifier), U[R].position.set(ne.pageX, ne.pageY));
      }
      ((this._touchCount = D.length), this.viewer.emit(_.TOUCH_MOVE, m));
    }
    _onKeyDown(m) {
      ((this._keys[m.key] = !0), this.viewer.emit(_.KEYDOWN, m));
    }
    _onKeyPress(m) {
      ((this._keys[m.key] = !0), this.viewer.emit(_.KEYPRESS, m));
    }
    _onKeyUp(m) {
      ((this._keys[m.key] = !1), this.viewer.emit(_.KEYUP, m));
    }
  };
  (B(_, "CLICK", "click"),
    B(_, "MOUSE_WHEEL", "mousewheel"),
    B(_, "TOUCH_START", "touchstart"),
    B(_, "TOUCH_END", "touchend"),
    B(_, "TOUCH_MOVE", "touchmove"),
    B(_, "POINTER_DOWN", "pointerdown"),
    B(_, "POINTER_UP", "pointerup"),
    B(_, "POINTER_MOVE", "pointermove"),
    B(_, "POINTER_OVER", "pointerover"),
    B(_, "POINTER_OUT", "pointerout"),
    B(_, "KEYDOWN", "keydown"),
    B(_, "KEYPRESS", "keypress"),
    B(_, "KEYUP", "keyup"),
    B(_, "RESIZE", "resize"));
  let g = _;
};
