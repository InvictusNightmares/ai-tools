import { defineField as B } from "../fields.js";
// Recovered runtime module; preserve lazy initialization for cyclic dependencies.
export default (t, n, r) => {
  r.d(n, {
    M: () => Be,
    z: () => Re,
  });
  var s = r(694),
    h = r(25),
    l = r(313);
  const { clamp: g, degToRad: _, quarticDamp: A } = h.MathUtils,
    { abs: m, tan: D } = Math;
  let U = new h.FM8(),
    R = new h.FM8(),
    ne = new h.FM8(),
    ce = new h.FM8(),
    xe = new h.FM8(),
    Se = new h.Pa4(),
    $ = new h.Pa4(),
    q = new h.Pa4(),
    N = new h.Pa4(),
    ie = new h.Pa4(),
    _e = new h._fP(),
    Pe = new h.$V();
  var Be;
  (function (ct) {
    ((ct[(ct.FREE = 0)] = "FREE"), (ct[(ct.TRANSLATE = 1)] = "TRANSLATE"));
  })(Be || (Be = {}));
  class Re extends l._ {
    constructor() {
      super(...arguments);
      B(this, "_button", -1);
      B(this, "_touchID", -1);
      B(this, "_distanceDelta", 0);
      B(this, "_preLoc0", new h.FM8());
      B(this, "_preLoc1", new h.FM8());
      B(this, "_rotateDelta", new h.FM8());
      B(this, "_panDelta", new h.FM8());
      B(this, "mode", Be.FREE);
      B(this, "forbidX", !1);
      B(this, "forbidY", !1);
      B(this, "forbidZ", !1);
      B(this, "forbidPanX", !1);
      B(this, "forbidPanY", !1);
      B(this, "rotateSpeed", 2);
      B(this, "rotateSmoothing", 0.5);
      B(this, "panSpeed", 2);
      B(this, "panSmoothing", 0.5);
      B(this, "phiMin", 0.001);
      B(this, "phiMax", Math.PI - 0.001);
      B(this, "thetaMin", -1 / 0);
      B(this, "thetaMax", 1 / 0);
      B(this, "distanceMin", 0.001);
      B(this, "distanceMax", 1 / 0);
      B(this, "rotateTouchID", 0);
    }
    onEnable() {
      (this.viewer.on(s.i.POINTER_DOWN, this._onPointerDown, this),
        this.viewer.on(s.i.POINTER_UP, this._onPointerUp, this),
        this.viewer.on(s.i.POINTER_MOVE, this._onPointerMove, this),
        this.viewer.on(s.i.MOUSE_WHEEL, this._onMouseWheel, this),
        this.viewer.on(s.i.TOUCH_START, this._onTouchStart, this),
        this.viewer.on(s.i.TOUCH_MOVE, this._onTouchMove, this),
        this.reset());
    }
    onDisable() {
      (this.viewer.off(s.i.POINTER_DOWN, this._onPointerDown, this),
        this.viewer.off(s.i.POINTER_UP, this._onPointerUp, this),
        this.viewer.off(s.i.POINTER_MOVE, this._onPointerMove, this),
        this.viewer.off(s.i.MOUSE_WHEEL, this._onMouseWheel, this),
        this.viewer.off(s.i.TOUCH_START, this._onTouchStart, this),
        this.viewer.off(s.i.TOUCH_MOVE, this._onTouchMove, this));
    }
    reset() {
      ((this._button = -1),
        (this._touchID = -1),
        this._rotateDelta.set(0, 0),
        this._panDelta.set(0, 0),
        (this._distanceDelta = 0));
    }
    _onPointerDown(Ze) {
      this.viewer.brower.isMobile ||
        ((this._button = Ze.button), this._preLoc0.set(Ze.pageX, Ze.pageY));
    }
    _onPointerUp(Ze) {
      this.viewer.brower.isMobile || (this._button = -1);
    }
    _onPointerMove(Ze) {
      if (!this.viewer.brower.isMobile) {
        switch ((U.set(Ze.pageX, Ze.pageY), this._button)) {
          case 0:
            this._rotateDelta.add(this._calculateRotateDelta(xe, this._preLoc0, U));
            break;
          case 1:
            this._panDelta.add(this._calculatePanDelta(xe, this._preLoc0, U));
            break;
        }
        this._preLoc0.copy(U);
      }
    }
    _onMouseWheel(Ze) {
      if (this.lookAt) {
        let Nt = Se.copy(this.lookAt.position)
            .add(this.trackedObjectOffset)
            .distanceTo(this.node.position),
          Bt = Nt + this._distanceDelta;
        (Ze.deltaY > 0
          ? (Bt *= this._calculateDistanceScale(1 / 0.85))
          : Ze.deltaY < 0 && (Bt *= this._calculateDistanceScale(0.85)),
          (this._distanceDelta = Bt - Nt));
      }
    }
    _onTouchStart(Ze) {
      if (!this.viewer.brower.isMobile) return;
      let Nt = Ze.touches,
        Bt = this.rotateTouchID;
      Nt.length > Bt + 1
        ? (this._preLoc0.set(Nt[Bt].pageX, Nt[Bt].pageY),
          this._preLoc1.set(Nt[Bt + 1].pageX, Nt[Bt + 1].pageY))
        : Nt.length > Bt &&
          ((this._touchID = Nt[Bt].identifier), this._preLoc0.set(Nt[Bt].pageX, Nt[Bt].pageY));
    }
    _onTouchMove(Ze) {
      if (!this.viewer.brower.isMobile) return;
      let Nt = Ze.touches,
        Bt = this.rotateTouchID;
      if (Nt.length > Bt + 1) {
        if (
          (U.set(Nt[Bt].pageX, Nt[Bt].pageY),
          R.set(Nt[Bt + 1].pageX, Nt[Bt + 1].pageY),
          this.lookAt)
        ) {
          let en = Se.copy(this.lookAt.position)
              .add(this.trackedObjectOffset)
              .distanceTo(this.node.position),
            li =
              (en + this._distanceDelta) *
              this._calculateDistanceScale(
                this._preLoc0.distanceTo(this._preLoc1) / U.distanceTo(R),
              );
          this._distanceDelta = li - en;
        }
        (this._panDelta.add(
          this._calculatePanDelta(
            xe,
            ce.copy(this._preLoc0).add(this._preLoc1).multiplyScalar(0.5),
            ne.copy(U).add(R).multiplyScalar(0.5),
          ),
        ),
          this._preLoc0.copy(U),
          this._preLoc1.copy(R));
      } else
        Nt.length > Bt &&
          this._touchID === Nt[Bt].identifier &&
          (U.set(Nt[Bt].pageX, Nt[Bt].pageY),
          this._rotateDelta.add(this._calculateRotateDelta(xe, this._preLoc0, U)),
          this._preLoc0.copy(U));
    }
    _calculateDistanceScale(Ze) {
      return (this.forbidZ && (Ze = 1), Ze);
    }
    _calculateRotateDelta(Ze, Nt, Bt) {
      let en = this.viewer.renderer.domElement;
      return (
        Ze.copy(Bt)
          .sub(Nt)
          .multiplyScalar((this.rotateSpeed * 2 * Math.PI) / en.height),
        (Ze.y = -Ze.y),
        this.forbidX && (Ze.x = 0),
        this.forbidY && (Ze.y = 0),
        Ze
      );
    }
    _calculatePanDelta(Ze, Nt, Bt) {
      let en = this.viewer.renderer.domElement;
      return (
        Ze.copy(Bt)
          .sub(Nt)
          .multiplyScalar(this.panSpeed / en.height),
        this.forbidPanX && (Ze.x = 0),
        this.forbidPanY && (Ze.y = 0),
        Ze
      );
    }
    update(Ze) {
      if (this.lookAt) {
        switch ((Se.copy(this.lookAt.position).add(this.trackedObjectOffset), this.mode)) {
          case Be.FREE:
            if (m(this._rotateDelta.x) + m(this._rotateDelta.y) + m(this._distanceDelta) > 0.001) {
              (_e.setFromUnitVectors(this.node.up, h.Tme.DEFAULT_UP),
                $.copy(this.node.position).sub(Se),
                $.applyQuaternion(_e),
                Pe.setFromVector3($));
              let Nt = A(1, 0, this.rotateSmoothing, Ze);
              ((this._rotateDelta.x =
                Pe.theta - g(Pe.theta - this._rotateDelta.x, this.thetaMin, this.thetaMax)),
                (Pe.theta = Pe.theta - this._rotateDelta.x * (1 - Nt)),
                (this._rotateDelta.y =
                  g(Pe.phi + this._rotateDelta.y, this.phiMin, this.phiMax) - Pe.phi),
                (Pe.phi = g(Pe.phi + this._rotateDelta.y * (1 - Nt), 0.001, Math.PI - 0.001)),
                (this._distanceDelta =
                  g(Pe.radius + this._distanceDelta, this.distanceMin, this.distanceMax) -
                  Pe.radius),
                (Pe.radius = Pe.radius + this._distanceDelta * (1 - Nt)),
                this._rotateDelta.multiplyScalar(Nt),
                (this._distanceDelta *= Nt),
                $.setFromSpherical(Pe),
                $.applyQuaternion(_e.invert()),
                this.node.position.copy($.add(Se)));
            }
            break;
          case Be.TRANSLATE:
            if (m(this._distanceDelta) > 0.001) {
              $.copy(this.node.position).sub(this.lookAt.position);
              let Nt = A(1, 0, this.rotateSmoothing, Ze),
                Bt = $.length();
              this._distanceDelta =
                g(Bt + this._distanceDelta, this.distanceMin, this.distanceMax) - Bt;
              let en = Bt + this._distanceDelta * (1 - Nt);
              this._distanceDelta *= Nt;
              let li = $.normalize().multiplyScalar(en).add(this.lookAt.position);
              (q.copy(li).sub(this.node.position),
                this.trackedObjectOffset.add(q),
                this.node.position.copy(li),
                Se.copy(this.lookAt.position).add(this.trackedObjectOffset));
            }
            break;
        }
        switch (this.mode) {
          case Be.FREE:
          case Be.TRANSLATE: {
            if (m(this._panDelta.x) + m(this._panDelta.y) > 0.001) {
              ($.copy(this.node.position).sub(Se),
                N.setFromMatrixColumn(this.node.matrix, 0),
                ie.setFromMatrixColumn(this.node.matrix, 1));
              let Nt = $.length() * 2 * D(_(this.fov * 0.5)),
                Bt = A(1, 0, this.panSmoothing, Ze),
                en = this.trackedObjectOffset;
              (en.sub(N.multiplyScalar(this._panDelta.x * Nt * (1 - Bt))),
                en.add(ie.multiplyScalar(this._panDelta.y * Nt * (1 - Bt))),
                this._panDelta.multiplyScalar(Bt),
                Se.copy(this.lookAt.position).add(en),
                this.node.position.copy($.add(Se)));
            }
            this.node.lookAt(Se);
            break;
          }
        }
      }
    }
  }
};
