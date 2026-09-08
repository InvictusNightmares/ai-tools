import { defineField as B } from "../fields.js";
// Recovered runtime module; preserve lazy initialization for cyclic dependencies.
export default (t, n, r) => {
  r.d(n, {
    Ys: () => ne,
  });
  var s = r(477);
  const h = new s.iMs(),
    l = new s.Pa4(),
    g = new s.Pa4(),
    _ = new s._fP(),
    A = {
      X: new s.Pa4(1, 0, 0),
      Y: new s.Pa4(0, 1, 0),
      Z: new s.Pa4(0, 0, 1),
    },
    m = {
      type: "change",
    },
    D = {
      type: "mouseDown",
    },
    U = {
      type: "mouseUp",
      mode: null,
    },
    R = {
      type: "objectChange",
    };
  class ne extends s.Tme {
    constructor(Ft, jt) {
      (super(),
        jt === void 0 &&
          (console.warn(
            'THREE.TransformControls: The second parameter "domElement" is now mandatory.',
          ),
          (jt = document)),
        (this.isTransformControls = !0),
        (this.visible = !1),
        (this.domElement = jt),
        (this.domElement.style.touchAction = "none"));
      const Xt = new zt();
      ((this._gizmo = Xt), this.add(Xt));
      const Rt = new Sn();
      ((this._plane = Rt), this.add(Rt));
      const Wn = this;
      function He(On, kn) {
        let bi = kn;
        (Object.defineProperty(Wn, On, {
          get: function () {
            return bi !== void 0 ? bi : kn;
          },
          set: function ($i) {
            bi !== $i &&
              ((bi = $i),
              (Rt[On] = $i),
              (Xt[On] = $i),
              Wn.dispatchEvent({
                type: On + "-changed",
                value: $i,
              }),
              Wn.dispatchEvent(m));
          },
        }),
          (Wn[On] = kn),
          (Rt[On] = kn),
          (Xt[On] = kn));
      }
      (He("camera", Ft),
        He("object", void 0),
        He("enabled", !0),
        He("axis", null),
        He("mode", "translate"),
        He("translationSnap", null),
        He("rotationSnap", null),
        He("scaleSnap", null),
        He("space", "world"),
        He("size", 1),
        He("dragging", !1),
        He("showX", !0),
        He("showY", !0),
        He("showZ", !0));
      const pt = new s.Pa4(),
        Fe = new s.Pa4(),
        qe = new s._fP(),
        wt = new s._fP(),
        An = new s.Pa4(),
        Qt = new s._fP(),
        Pi = new s.Pa4(),
        ui = new s.Pa4(),
        mi = new s.Pa4(),
        Si = 0,
        Gt = new s.Pa4();
      (He("worldPosition", pt),
        He("worldPositionStart", Fe),
        He("worldQuaternion", qe),
        He("worldQuaternionStart", wt),
        He("cameraPosition", An),
        He("cameraQuaternion", Qt),
        He("pointStart", Pi),
        He("pointEnd", ui),
        He("rotationAxis", mi),
        He("rotationAngle", Si),
        He("eye", Gt),
        (this._offset = new s.Pa4()),
        (this._startNorm = new s.Pa4()),
        (this._endNorm = new s.Pa4()),
        (this._cameraScale = new s.Pa4()),
        (this._parentPosition = new s.Pa4()),
        (this._parentQuaternion = new s._fP()),
        (this._parentQuaternionInv = new s._fP()),
        (this._parentScale = new s.Pa4()),
        (this._worldScaleStart = new s.Pa4()),
        (this._worldQuaternionInv = new s._fP()),
        (this._worldScale = new s.Pa4()),
        (this._positionStart = new s.Pa4()),
        (this._quaternionStart = new s._fP()),
        (this._scaleStart = new s.Pa4()),
        (this._getPointer = ce.bind(this)),
        (this._onPointerDown = Se.bind(this)),
        (this._onPointerHover = xe.bind(this)),
        (this._onPointerMove = $.bind(this)),
        (this._onPointerUp = q.bind(this)),
        this.domElement.addEventListener("pointerdown", this._onPointerDown),
        this.domElement.addEventListener("pointermove", this._onPointerHover),
        this.domElement.addEventListener("pointerup", this._onPointerUp));
    }
    updateMatrixWorld() {
      (this.object !== void 0 &&
        (this.object.updateMatrixWorld(),
        this.object.parent === null
          ? console.error(
              "TransformControls: The attached 3D object must be a part of the scene graph.",
            )
          : this.object.parent.matrixWorld.decompose(
              this._parentPosition,
              this._parentQuaternion,
              this._parentScale,
            ),
        this.object.matrixWorld.decompose(
          this.worldPosition,
          this.worldQuaternion,
          this._worldScale,
        ),
        this._parentQuaternionInv.copy(this._parentQuaternion).invert(),
        this._worldQuaternionInv.copy(this.worldQuaternion).invert()),
        this.camera.updateMatrixWorld(),
        this.camera.matrixWorld.decompose(
          this.cameraPosition,
          this.cameraQuaternion,
          this._cameraScale,
        ),
        this.camera.isOrthographicCamera
          ? this.camera.getWorldDirection(this.eye).negate()
          : this.eye.copy(this.cameraPosition).sub(this.worldPosition).normalize(),
        super.updateMatrixWorld(this));
    }
    pointerHover(Ft) {
      if (this.object === void 0 || this.dragging === !0) return;
      h.setFromCamera(Ft, this.camera);
      const jt = N(this._gizmo.picker[this.mode], h);
      jt ? (this.axis = jt.object.name) : (this.axis = null);
    }
    pointerDown(Ft) {
      if (
        !(this.object === void 0 || this.dragging === !0 || Ft.button !== 0) &&
        this.axis !== null
      ) {
        h.setFromCamera(Ft, this.camera);
        const jt = N(this._plane, h, !0);
        (jt &&
          (this.object.updateMatrixWorld(),
          this.object.parent.updateMatrixWorld(),
          this._positionStart.copy(this.object.position),
          this._quaternionStart.copy(this.object.quaternion),
          this._scaleStart.copy(this.object.scale),
          this.object.matrixWorld.decompose(
            this.worldPositionStart,
            this.worldQuaternionStart,
            this._worldScaleStart,
          ),
          this.pointStart.copy(jt.point).sub(this.worldPositionStart)),
          (this.dragging = !0),
          (D.mode = this.mode),
          this.dispatchEvent(D));
      }
    }
    pointerMove(Ft) {
      const jt = this.axis,
        Xt = this.mode,
        Rt = this.object;
      let Wn = this.space;
      if (
        (Xt === "scale"
          ? (Wn = "local")
          : (jt === "E" || jt === "XYZE" || jt === "XYZ") && (Wn = "world"),
        Rt === void 0 || jt === null || this.dragging === !1 || Ft.button !== -1)
      )
        return;
      h.setFromCamera(Ft, this.camera);
      const He = N(this._plane, h, !0);
      if (He) {
        if ((this.pointEnd.copy(He.point).sub(this.worldPositionStart), Xt === "translate"))
          (this._offset.copy(this.pointEnd).sub(this.pointStart),
            Wn === "local" &&
              jt !== "XYZ" &&
              this._offset.applyQuaternion(this._worldQuaternionInv),
            jt.indexOf("X") === -1 && (this._offset.x = 0),
            jt.indexOf("Y") === -1 && (this._offset.y = 0),
            jt.indexOf("Z") === -1 && (this._offset.z = 0),
            Wn === "local" && jt !== "XYZ"
              ? this._offset.applyQuaternion(this._quaternionStart).divide(this._parentScale)
              : this._offset.applyQuaternion(this._parentQuaternionInv).divide(this._parentScale),
            Rt.position.copy(this._offset).add(this._positionStart),
            this.translationSnap &&
              (Wn === "local" &&
                (Rt.position.applyQuaternion(_.copy(this._quaternionStart).invert()),
                jt.search("X") !== -1 &&
                  (Rt.position.x =
                    Math.round(Rt.position.x / this.translationSnap) * this.translationSnap),
                jt.search("Y") !== -1 &&
                  (Rt.position.y =
                    Math.round(Rt.position.y / this.translationSnap) * this.translationSnap),
                jt.search("Z") !== -1 &&
                  (Rt.position.z =
                    Math.round(Rt.position.z / this.translationSnap) * this.translationSnap),
                Rt.position.applyQuaternion(this._quaternionStart)),
              Wn === "world" &&
                (Rt.parent && Rt.position.add(l.setFromMatrixPosition(Rt.parent.matrixWorld)),
                jt.search("X") !== -1 &&
                  (Rt.position.x =
                    Math.round(Rt.position.x / this.translationSnap) * this.translationSnap),
                jt.search("Y") !== -1 &&
                  (Rt.position.y =
                    Math.round(Rt.position.y / this.translationSnap) * this.translationSnap),
                jt.search("Z") !== -1 &&
                  (Rt.position.z =
                    Math.round(Rt.position.z / this.translationSnap) * this.translationSnap),
                Rt.parent && Rt.position.sub(l.setFromMatrixPosition(Rt.parent.matrixWorld)))));
        else if (Xt === "scale") {
          if (jt.search("XYZ") !== -1) {
            let pt = this.pointEnd.length() / this.pointStart.length();
            (this.pointEnd.dot(this.pointStart) < 0 && (pt *= -1), g.set(pt, pt, pt));
          } else
            (l.copy(this.pointStart),
              g.copy(this.pointEnd),
              l.applyQuaternion(this._worldQuaternionInv),
              g.applyQuaternion(this._worldQuaternionInv),
              g.divide(l),
              jt.search("X") === -1 && (g.x = 1),
              jt.search("Y") === -1 && (g.y = 1),
              jt.search("Z") === -1 && (g.z = 1));
          (Rt.scale.copy(this._scaleStart).multiply(g),
            this.scaleSnap &&
              (jt.search("X") !== -1 &&
                (Rt.scale.x =
                  Math.round(Rt.scale.x / this.scaleSnap) * this.scaleSnap || this.scaleSnap),
              jt.search("Y") !== -1 &&
                (Rt.scale.y =
                  Math.round(Rt.scale.y / this.scaleSnap) * this.scaleSnap || this.scaleSnap),
              jt.search("Z") !== -1 &&
                (Rt.scale.z =
                  Math.round(Rt.scale.z / this.scaleSnap) * this.scaleSnap || this.scaleSnap)));
        } else if (Xt === "rotate") {
          this._offset.copy(this.pointEnd).sub(this.pointStart);
          const pt =
            20 / this.worldPosition.distanceTo(l.setFromMatrixPosition(this.camera.matrixWorld));
          (jt === "E"
            ? (this.rotationAxis.copy(this.eye),
              (this.rotationAngle = this.pointEnd.angleTo(this.pointStart)),
              this._startNorm.copy(this.pointStart).normalize(),
              this._endNorm.copy(this.pointEnd).normalize(),
              (this.rotationAngle *=
                this._endNorm.cross(this._startNorm).dot(this.eye) < 0 ? 1 : -1))
            : jt === "XYZE"
              ? (this.rotationAxis.copy(this._offset).cross(this.eye).normalize(),
                (this.rotationAngle =
                  this._offset.dot(l.copy(this.rotationAxis).cross(this.eye)) * pt))
              : (jt === "X" || jt === "Y" || jt === "Z") &&
                (this.rotationAxis.copy(A[jt]),
                l.copy(A[jt]),
                Wn === "local" && l.applyQuaternion(this.worldQuaternion),
                (this.rotationAngle = this._offset.dot(l.cross(this.eye).normalize()) * pt)),
            this.rotationSnap &&
              (this.rotationAngle =
                Math.round(this.rotationAngle / this.rotationSnap) * this.rotationSnap),
            Wn === "local" && jt !== "E" && jt !== "XYZE"
              ? (Rt.quaternion.copy(this._quaternionStart),
                Rt.quaternion
                  .multiply(_.setFromAxisAngle(this.rotationAxis, this.rotationAngle))
                  .normalize())
              : (this.rotationAxis.applyQuaternion(this._parentQuaternionInv),
                Rt.quaternion.copy(_.setFromAxisAngle(this.rotationAxis, this.rotationAngle)),
                Rt.quaternion.multiply(this._quaternionStart).normalize()));
        }
        (this.dispatchEvent(m), this.dispatchEvent(R));
      }
    }
    pointerUp(Ft) {
      Ft.button === 0 &&
        (this.dragging && this.axis !== null && ((U.mode = this.mode), this.dispatchEvent(U)),
        (this.dragging = !1),
        (this.axis = null));
    }
    dispose() {
      (this.domElement.removeEventListener("pointerdown", this._onPointerDown),
        this.domElement.removeEventListener("pointermove", this._onPointerHover),
        this.domElement.removeEventListener("pointermove", this._onPointerMove),
        this.domElement.removeEventListener("pointerup", this._onPointerUp),
        this.traverse(function (Ft) {
          (Ft.geometry && Ft.geometry.dispose(), Ft.material && Ft.material.dispose());
        }));
    }
    attach(Ft) {
      return ((this.object = Ft), (this.visible = !0), this);
    }
    detach() {
      return ((this.object = void 0), (this.visible = !1), (this.axis = null), this);
    }
    reset() {
      this.enabled &&
        this.dragging &&
        (this.object.position.copy(this._positionStart),
        this.object.quaternion.copy(this._quaternionStart),
        this.object.scale.copy(this._scaleStart),
        this.dispatchEvent(m),
        this.dispatchEvent(R),
        this.pointStart.copy(this.pointEnd));
    }
    getRaycaster() {
      return h;
    }
    getMode() {
      return this.mode;
    }
    setMode(Ft) {
      this.mode = Ft;
    }
    setTranslationSnap(Ft) {
      this.translationSnap = Ft;
    }
    setRotationSnap(Ft) {
      this.rotationSnap = Ft;
    }
    setScaleSnap(Ft) {
      this.scaleSnap = Ft;
    }
    setSize(Ft) {
      this.size = Ft;
    }
    setSpace(Ft) {
      this.space = Ft;
    }
  }
  function ce(rn) {
    if (this.domElement.ownerDocument.pointerLockElement)
      return {
        x: 0,
        y: 0,
        button: rn.button,
      };
    {
      const Ft = this.domElement.getBoundingClientRect();
      return {
        x: ((rn.clientX - Ft.left) / Ft.width) * 2 - 1,
        y: (-(rn.clientY - Ft.top) / Ft.height) * 2 + 1,
        button: rn.button,
      };
    }
  }
  function xe(rn) {
    if (this.enabled)
      switch (rn.pointerType) {
        case "mouse":
        case "pen":
          this.pointerHover(this._getPointer(rn));
          break;
      }
  }
  function Se(rn) {
    this.enabled &&
      (document.pointerLockElement || this.domElement.setPointerCapture(rn.pointerId),
      this.domElement.addEventListener("pointermove", this._onPointerMove),
      this.pointerHover(this._getPointer(rn)),
      this.pointerDown(this._getPointer(rn)));
  }
  function $(rn) {
    this.enabled && this.pointerMove(this._getPointer(rn));
  }
  function q(rn) {
    this.enabled &&
      (this.domElement.releasePointerCapture(rn.pointerId),
      this.domElement.removeEventListener("pointermove", this._onPointerMove),
      this.pointerUp(this._getPointer(rn)));
  }
  function N(rn, Ft, jt) {
    const Xt = Ft.intersectObject(rn, !0);
    for (let Rt = 0; Rt < Xt.length; Rt++) if (Xt[Rt].object.visible || jt) return Xt[Rt];
    return !1;
  }
  const ie = new s.USm(),
    _e = new s.Pa4(0, 1, 0),
    Pe = new s.Pa4(0, 0, 0),
    Be = new s.yGw(),
    Re = new s._fP(),
    ct = new s._fP(),
    et = new s.Pa4(),
    Ze = new s.yGw(),
    Nt = new s.Pa4(1, 0, 0),
    Bt = new s.Pa4(0, 1, 0),
    en = new s.Pa4(0, 0, 1),
    li = new s.Pa4(),
    di = new s.Pa4(),
    xi = new s.Pa4();
  class zt extends s.Tme {
    constructor() {
      (super(), (this.isTransformControlsGizmo = !0), (this.type = "TransformControlsGizmo"));
      const Ft = new s.vBJ({
          depthTest: !1,
          depthWrite: !1,
          fog: !1,
          toneMapped: !1,
          transparent: !0,
        }),
        jt = new s.nls({
          depthTest: !1,
          depthWrite: !1,
          fog: !1,
          toneMapped: !1,
          transparent: !0,
        }),
        Xt = Ft.clone();
      Xt.opacity = 0.15;
      const Rt = jt.clone();
      Rt.opacity = 0.5;
      const Wn = Ft.clone();
      Wn.color.setHex(16711680);
      const He = Ft.clone();
      He.color.setHex(65280);
      const pt = Ft.clone();
      pt.color.setHex(255);
      const Fe = Ft.clone();
      (Fe.color.setHex(16711680), (Fe.opacity = 0.5));
      const qe = Ft.clone();
      (qe.color.setHex(65280), (qe.opacity = 0.5));
      const wt = Ft.clone();
      (wt.color.setHex(255), (wt.opacity = 0.5));
      const An = Ft.clone();
      An.opacity = 0.25;
      const Qt = Ft.clone();
      (Qt.color.setHex(16776960), (Qt.opacity = 0.25), Ft.clone().color.setHex(16776960));
      const ui = Ft.clone();
      ui.color.setHex(7895160);
      const mi = new s.fHI(0, 0.04, 0.1, 12);
      mi.translate(0, 0.05, 0);
      const Si = new s.DvJ(0.08, 0.08, 0.08);
      Si.translate(0, 0.04, 0);
      const Gt = new s.u9r();
      Gt.setAttribute("position", new s.a$l([0, 0, 0, 1, 0, 0], 3));
      const On = new s.fHI(0.0075, 0.0075, 0.5, 3);
      On.translate(0, 0.25, 0);
      function kn(Ti, gi) {
        const qi = new s.XvJ(Ti, 0.0075, 3, 64, gi * Math.PI * 2);
        return (qi.rotateY(Math.PI / 2), qi.rotateX(Math.PI / 2), qi);
      }
      function bi() {
        const Ti = new s.u9r();
        return (Ti.setAttribute("position", new s.a$l([0, 0, 0, 1, 1, 1], 3)), Ti);
      }
      const $i = {
          X: [
            [new s.Kj0(mi, Wn), [0.5, 0, 0], [0, 0, -Math.PI / 2]],
            [new s.Kj0(mi, Wn), [-0.5, 0, 0], [0, 0, Math.PI / 2]],
            [new s.Kj0(On, Wn), [0, 0, 0], [0, 0, -Math.PI / 2]],
          ],
          Y: [
            [new s.Kj0(mi, He), [0, 0.5, 0]],
            [new s.Kj0(mi, He), [0, -0.5, 0], [Math.PI, 0, 0]],
            [new s.Kj0(On, He)],
          ],
          Z: [
            [new s.Kj0(mi, pt), [0, 0, 0.5], [Math.PI / 2, 0, 0]],
            [new s.Kj0(mi, pt), [0, 0, -0.5], [-Math.PI / 2, 0, 0]],
            [new s.Kj0(On, pt), null, [Math.PI / 2, 0, 0]],
          ],
          XYZ: [[new s.Kj0(new s.pQR(0.1, 0), An.clone()), [0, 0, 0]]],
          XY: [[new s.Kj0(new s.DvJ(0.15, 0.15, 0.01), wt.clone()), [0.15, 0.15, 0]]],
          YZ: [
            [
              new s.Kj0(new s.DvJ(0.15, 0.15, 0.01), Fe.clone()),
              [0, 0.15, 0.15],
              [0, Math.PI / 2, 0],
            ],
          ],
          XZ: [
            [
              new s.Kj0(new s.DvJ(0.15, 0.15, 0.01), qe.clone()),
              [0.15, 0, 0.15],
              [-Math.PI / 2, 0, 0],
            ],
          ],
        },
        zr = {
          X: [
            [new s.Kj0(new s.fHI(0.2, 0, 0.6, 4), Xt), [0.3, 0, 0], [0, 0, -Math.PI / 2]],
            [new s.Kj0(new s.fHI(0.2, 0, 0.6, 4), Xt), [-0.3, 0, 0], [0, 0, Math.PI / 2]],
          ],
          Y: [
            [new s.Kj0(new s.fHI(0.2, 0, 0.6, 4), Xt), [0, 0.3, 0]],
            [new s.Kj0(new s.fHI(0.2, 0, 0.6, 4), Xt), [0, -0.3, 0], [0, 0, Math.PI]],
          ],
          Z: [
            [new s.Kj0(new s.fHI(0.2, 0, 0.6, 4), Xt), [0, 0, 0.3], [Math.PI / 2, 0, 0]],
            [new s.Kj0(new s.fHI(0.2, 0, 0.6, 4), Xt), [0, 0, -0.3], [-Math.PI / 2, 0, 0]],
          ],
          XYZ: [[new s.Kj0(new s.pQR(0.2, 0), Xt)]],
          XY: [[new s.Kj0(new s.DvJ(0.2, 0.2, 0.01), Xt), [0.15, 0.15, 0]]],
          YZ: [[new s.Kj0(new s.DvJ(0.2, 0.2, 0.01), Xt), [0, 0.15, 0.15], [0, Math.PI / 2, 0]]],
          XZ: [[new s.Kj0(new s.DvJ(0.2, 0.2, 0.01), Xt), [0.15, 0, 0.15], [-Math.PI / 2, 0, 0]]],
        },
        Fi = {
          START: [[new s.Kj0(new s.pQR(0.01, 2), Rt), null, null, null, "helper"]],
          END: [[new s.Kj0(new s.pQR(0.01, 2), Rt), null, null, null, "helper"]],
          DELTA: [[new s.x12(bi(), Rt), null, null, null, "helper"]],
          X: [[new s.x12(Gt, Rt.clone()), [-1e3, 0, 0], null, [1e6, 1, 1], "helper"]],
          Y: [
            [new s.x12(Gt, Rt.clone()), [0, -1e3, 0], [0, 0, Math.PI / 2], [1e6, 1, 1], "helper"],
          ],
          Z: [
            [new s.x12(Gt, Rt.clone()), [0, 0, -1e3], [0, -Math.PI / 2, 0], [1e6, 1, 1], "helper"],
          ],
        },
        vr = {
          XYZE: [[new s.Kj0(kn(0.5, 1), ui), null, [0, Math.PI / 2, 0]]],
          X: [[new s.Kj0(kn(0.5, 0.5), Wn)]],
          Y: [[new s.Kj0(kn(0.5, 0.5), He), null, [0, 0, -Math.PI / 2]]],
          Z: [[new s.Kj0(kn(0.5, 0.5), pt), null, [0, Math.PI / 2, 0]]],
          E: [[new s.Kj0(kn(0.75, 1), Qt), null, [0, Math.PI / 2, 0]]],
        },
        Oi = {
          AXIS: [[new s.x12(Gt, Rt.clone()), [-1e3, 0, 0], null, [1e6, 1, 1], "helper"]],
        },
        ts = {
          XYZE: [[new s.Kj0(new s.xo$(0.25, 10, 8), Xt)]],
          X: [
            [new s.Kj0(new s.XvJ(0.5, 0.1, 4, 24), Xt), [0, 0, 0], [0, -Math.PI / 2, -Math.PI / 2]],
          ],
          Y: [[new s.Kj0(new s.XvJ(0.5, 0.1, 4, 24), Xt), [0, 0, 0], [Math.PI / 2, 0, 0]]],
          Z: [[new s.Kj0(new s.XvJ(0.5, 0.1, 4, 24), Xt), [0, 0, 0], [0, 0, -Math.PI / 2]]],
          E: [[new s.Kj0(new s.XvJ(0.75, 0.1, 2, 24), Xt)]],
        },
        Gr = {
          X: [
            [new s.Kj0(Si, Wn), [0.5, 0, 0], [0, 0, -Math.PI / 2]],
            [new s.Kj0(On, Wn), [0, 0, 0], [0, 0, -Math.PI / 2]],
            [new s.Kj0(Si, Wn), [-0.5, 0, 0], [0, 0, Math.PI / 2]],
          ],
          Y: [
            [new s.Kj0(Si, He), [0, 0.5, 0]],
            [new s.Kj0(On, He)],
            [new s.Kj0(Si, He), [0, -0.5, 0], [0, 0, Math.PI]],
          ],
          Z: [
            [new s.Kj0(Si, pt), [0, 0, 0.5], [Math.PI / 2, 0, 0]],
            [new s.Kj0(On, pt), [0, 0, 0], [Math.PI / 2, 0, 0]],
            [new s.Kj0(Si, pt), [0, 0, -0.5], [-Math.PI / 2, 0, 0]],
          ],
          XY: [[new s.Kj0(new s.DvJ(0.15, 0.15, 0.01), wt), [0.15, 0.15, 0]]],
          YZ: [[new s.Kj0(new s.DvJ(0.15, 0.15, 0.01), Fe), [0, 0.15, 0.15], [0, Math.PI / 2, 0]]],
          XZ: [[new s.Kj0(new s.DvJ(0.15, 0.15, 0.01), qe), [0.15, 0, 0.15], [-Math.PI / 2, 0, 0]]],
          XYZ: [[new s.Kj0(new s.DvJ(0.1, 0.1, 0.1), An.clone())]],
        },
        ys = {
          X: [
            [new s.Kj0(new s.fHI(0.2, 0, 0.6, 4), Xt), [0.3, 0, 0], [0, 0, -Math.PI / 2]],
            [new s.Kj0(new s.fHI(0.2, 0, 0.6, 4), Xt), [-0.3, 0, 0], [0, 0, Math.PI / 2]],
          ],
          Y: [
            [new s.Kj0(new s.fHI(0.2, 0, 0.6, 4), Xt), [0, 0.3, 0]],
            [new s.Kj0(new s.fHI(0.2, 0, 0.6, 4), Xt), [0, -0.3, 0], [0, 0, Math.PI]],
          ],
          Z: [
            [new s.Kj0(new s.fHI(0.2, 0, 0.6, 4), Xt), [0, 0, 0.3], [Math.PI / 2, 0, 0]],
            [new s.Kj0(new s.fHI(0.2, 0, 0.6, 4), Xt), [0, 0, -0.3], [-Math.PI / 2, 0, 0]],
          ],
          XY: [[new s.Kj0(new s.DvJ(0.2, 0.2, 0.01), Xt), [0.15, 0.15, 0]]],
          YZ: [[new s.Kj0(new s.DvJ(0.2, 0.2, 0.01), Xt), [0, 0.15, 0.15], [0, Math.PI / 2, 0]]],
          XZ: [[new s.Kj0(new s.DvJ(0.2, 0.2, 0.01), Xt), [0.15, 0, 0.15], [-Math.PI / 2, 0, 0]]],
          XYZ: [[new s.Kj0(new s.DvJ(0.2, 0.2, 0.2), Xt), [0, 0, 0]]],
        },
        xs = {
          X: [[new s.x12(Gt, Rt.clone()), [-1e3, 0, 0], null, [1e6, 1, 1], "helper"]],
          Y: [
            [new s.x12(Gt, Rt.clone()), [0, -1e3, 0], [0, 0, Math.PI / 2], [1e6, 1, 1], "helper"],
          ],
          Z: [
            [new s.x12(Gt, Rt.clone()), [0, 0, -1e3], [0, -Math.PI / 2, 0], [1e6, 1, 1], "helper"],
          ],
        };
      function hi(Ti) {
        const gi = new s.Tme();
        for (const qi in Ti)
          for (let ks = Ti[qi].length; ks--;) {
            const Gi = Ti[qi][ks][0].clone(),
              Ao = Ti[qi][ks][1],
              Hi = Ti[qi][ks][2],
              Us = Ti[qi][ks][3],
              Ba = Ti[qi][ks][4];
            ((Gi.name = qi),
              (Gi.tag = Ba),
              Ao && Gi.position.set(Ao[0], Ao[1], Ao[2]),
              Hi && Gi.rotation.set(Hi[0], Hi[1], Hi[2]),
              Us && Gi.scale.set(Us[0], Us[1], Us[2]),
              Gi.updateMatrix());
            const Fr = Gi.geometry.clone();
            (Fr.applyMatrix4(Gi.matrix),
              (Gi.geometry = Fr),
              (Gi.renderOrder = 1 / 0),
              Gi.position.set(0, 0, 0),
              Gi.rotation.set(0, 0, 0),
              Gi.scale.set(1, 1, 1),
              (Gi.isGizmo = !0),
              gi.add(Gi));
          }
        return gi;
      }
      ((this.gizmo = {}),
        (this.picker = {}),
        (this.helper = {}),
        this.add((this.gizmo.translate = hi($i))),
        this.add((this.gizmo.rotate = hi(vr))),
        this.add((this.gizmo.scale = hi(Gr))),
        this.add((this.picker.translate = hi(zr))),
        this.add((this.picker.rotate = hi(ts))),
        this.add((this.picker.scale = hi(ys))),
        this.add((this.helper.translate = hi(Fi))),
        this.add((this.helper.rotate = hi(Oi))),
        this.add((this.helper.scale = hi(xs))),
        (this.picker.translate.visible = !1),
        (this.picker.rotate.visible = !1),
        (this.picker.scale.visible = !1));
    }
    updateMatrixWorld(Ft) {
      const Xt =
        (this.mode === "scale" ? "local" : this.space) === "local" ? this.worldQuaternion : ct;
      ((this.gizmo.translate.visible = this.mode === "translate"),
        (this.gizmo.rotate.visible = this.mode === "rotate"),
        (this.gizmo.scale.visible = this.mode === "scale"),
        (this.helper.translate.visible = this.mode === "translate"),
        (this.helper.rotate.visible = this.mode === "rotate"),
        (this.helper.scale.visible = this.mode === "scale"));
      let Rt = [];
      ((Rt = Rt.concat(this.picker[this.mode].children)),
        (Rt = Rt.concat(this.gizmo[this.mode].children)),
        (Rt = Rt.concat(this.helper[this.mode].children)));
      for (let Wn = 0; Wn < Rt.length; Wn++) {
        const He = Rt[Wn];
        ((He.visible = !0), He.rotation.set(0, 0, 0), He.position.copy(this.worldPosition));
        let pt;
        if (
          (this.camera.isOrthographicCamera
            ? (pt = (this.camera.top - this.camera.bottom) / this.camera.zoom)
            : (pt =
                this.worldPosition.distanceTo(this.cameraPosition) *
                Math.min(
                  (1.9 * Math.tan((Math.PI * this.camera.fov) / 360)) / this.camera.zoom,
                  7,
                )),
          He.scale.set(1, 1, 1).multiplyScalar((pt * this.size) / 4),
          He.tag === "helper")
        ) {
          ((He.visible = !1),
            He.name === "AXIS"
              ? ((He.visible = !!this.axis),
                this.axis === "X" &&
                  (_.setFromEuler(ie.set(0, 0, 0)),
                  He.quaternion.copy(Xt).multiply(_),
                  Math.abs(_e.copy(Nt).applyQuaternion(Xt).dot(this.eye)) > 0.9 &&
                    (He.visible = !1)),
                this.axis === "Y" &&
                  (_.setFromEuler(ie.set(0, 0, Math.PI / 2)),
                  He.quaternion.copy(Xt).multiply(_),
                  Math.abs(_e.copy(Bt).applyQuaternion(Xt).dot(this.eye)) > 0.9 &&
                    (He.visible = !1)),
                this.axis === "Z" &&
                  (_.setFromEuler(ie.set(0, Math.PI / 2, 0)),
                  He.quaternion.copy(Xt).multiply(_),
                  Math.abs(_e.copy(en).applyQuaternion(Xt).dot(this.eye)) > 0.9 &&
                    (He.visible = !1)),
                this.axis === "XYZE" &&
                  (_.setFromEuler(ie.set(0, Math.PI / 2, 0)),
                  _e.copy(this.rotationAxis),
                  He.quaternion.setFromRotationMatrix(Be.lookAt(Pe, _e, Bt)),
                  He.quaternion.multiply(_),
                  (He.visible = this.dragging)),
                this.axis === "E" && (He.visible = !1))
              : He.name === "START"
                ? (He.position.copy(this.worldPositionStart), (He.visible = this.dragging))
                : He.name === "END"
                  ? (He.position.copy(this.worldPosition), (He.visible = this.dragging))
                  : He.name === "DELTA"
                    ? (He.position.copy(this.worldPositionStart),
                      He.quaternion.copy(this.worldQuaternionStart),
                      l
                        .set(1e-10, 1e-10, 1e-10)
                        .add(this.worldPositionStart)
                        .sub(this.worldPosition)
                        .multiplyScalar(-1),
                      l.applyQuaternion(this.worldQuaternionStart.clone().invert()),
                      He.scale.copy(l),
                      (He.visible = this.dragging))
                    : (He.quaternion.copy(Xt),
                      this.dragging
                        ? He.position.copy(this.worldPositionStart)
                        : He.position.copy(this.worldPosition),
                      this.axis && (He.visible = this.axis.search(He.name) !== -1)));
          continue;
        }
        (He.quaternion.copy(Xt),
          this.mode === "translate" || this.mode === "scale"
            ? (He.name === "X" &&
                Math.abs(_e.copy(Nt).applyQuaternion(Xt).dot(this.eye)) > 0.99 &&
                (He.scale.set(1e-10, 1e-10, 1e-10), (He.visible = !1)),
              He.name === "Y" &&
                Math.abs(_e.copy(Bt).applyQuaternion(Xt).dot(this.eye)) > 0.99 &&
                (He.scale.set(1e-10, 1e-10, 1e-10), (He.visible = !1)),
              He.name === "Z" &&
                Math.abs(_e.copy(en).applyQuaternion(Xt).dot(this.eye)) > 0.99 &&
                (He.scale.set(1e-10, 1e-10, 1e-10), (He.visible = !1)),
              He.name === "XY" &&
                Math.abs(_e.copy(en).applyQuaternion(Xt).dot(this.eye)) < 0.2 &&
                (He.scale.set(1e-10, 1e-10, 1e-10), (He.visible = !1)),
              He.name === "YZ" &&
                Math.abs(_e.copy(Nt).applyQuaternion(Xt).dot(this.eye)) < 0.2 &&
                (He.scale.set(1e-10, 1e-10, 1e-10), (He.visible = !1)),
              He.name === "XZ" &&
                Math.abs(_e.copy(Bt).applyQuaternion(Xt).dot(this.eye)) < 0.2 &&
                (He.scale.set(1e-10, 1e-10, 1e-10), (He.visible = !1)))
            : this.mode === "rotate" &&
              (Re.copy(Xt),
              _e.copy(this.eye).applyQuaternion(_.copy(Xt).invert()),
              He.name.search("E") !== -1 &&
                He.quaternion.setFromRotationMatrix(Be.lookAt(this.eye, Pe, Bt)),
              He.name === "X" &&
                (_.setFromAxisAngle(Nt, Math.atan2(-_e.y, _e.z)),
                _.multiplyQuaternions(Re, _),
                He.quaternion.copy(_)),
              He.name === "Y" &&
                (_.setFromAxisAngle(Bt, Math.atan2(_e.x, _e.z)),
                _.multiplyQuaternions(Re, _),
                He.quaternion.copy(_)),
              He.name === "Z" &&
                (_.setFromAxisAngle(en, Math.atan2(_e.y, _e.x)),
                _.multiplyQuaternions(Re, _),
                He.quaternion.copy(_))),
          (He.visible = He.visible && (He.name.indexOf("X") === -1 || this.showX)),
          (He.visible = He.visible && (He.name.indexOf("Y") === -1 || this.showY)),
          (He.visible = He.visible && (He.name.indexOf("Z") === -1 || this.showZ)),
          (He.visible =
            He.visible &&
            (He.name.indexOf("E") === -1 || (this.showX && this.showY && this.showZ))),
          (He.material._color = He.material._color || He.material.color.clone()),
          (He.material._opacity = He.material._opacity || He.material.opacity),
          He.material.color.copy(He.material._color),
          (He.material.opacity = He.material._opacity),
          this.enabled &&
            this.axis &&
            (He.name === this.axis ||
              this.axis.split("").some(function (Fe) {
                return He.name === Fe;
              })) &&
            (He.material.color.setHex(16776960), (He.material.opacity = 1)));
      }
      super.updateMatrixWorld(Ft);
    }
  }
  class Sn extends s.Kj0 {
    constructor() {
      (super(
        new s._12(1e5, 1e5, 2, 2),
        new s.vBJ({
          visible: !1,
          wireframe: !0,
          side: s.ehD,
          transparent: !0,
          opacity: 0.1,
          toneMapped: !1,
        }),
      ),
        (this.isTransformControlsPlane = !0),
        (this.type = "TransformControlsPlane"));
    }
    updateMatrixWorld(Ft) {
      let jt = this.space;
      switch (
        (this.position.copy(this.worldPosition),
        this.mode === "scale" && (jt = "local"),
        li.copy(Nt).applyQuaternion(jt === "local" ? this.worldQuaternion : ct),
        di.copy(Bt).applyQuaternion(jt === "local" ? this.worldQuaternion : ct),
        xi.copy(en).applyQuaternion(jt === "local" ? this.worldQuaternion : ct),
        _e.copy(di),
        this.mode)
      ) {
        case "translate":
        case "scale":
          switch (this.axis) {
            case "X":
              (_e.copy(this.eye).cross(li), et.copy(li).cross(_e));
              break;
            case "Y":
              (_e.copy(this.eye).cross(di), et.copy(di).cross(_e));
              break;
            case "Z":
              (_e.copy(this.eye).cross(xi), et.copy(xi).cross(_e));
              break;
            case "XY":
              et.copy(xi);
              break;
            case "YZ":
              et.copy(li);
              break;
            case "XZ":
              (_e.copy(xi), et.copy(di));
              break;
            case "XYZ":
            case "E":
              et.set(0, 0, 0);
              break;
          }
          break;
        case "rotate":
        default:
          et.set(0, 0, 0);
      }
      (et.length() === 0
        ? this.quaternion.copy(this.cameraQuaternion)
        : (Ze.lookAt(l.set(0, 0, 0), et, _e), this.quaternion.setFromRotationMatrix(Ze)),
        super.updateMatrixWorld(Ft));
    }
  }
};
