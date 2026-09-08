import {
  Component,
  Vector2,
  PerspectiveCamera,
  Plane,
  Matrix4,
  WebGLRenderTarget,
  LinearMipmapLinearFilter,
  ClampToEdgeWrapping,
  Vector3,
  Viewer,
  Quaternion,
  Vector4,
} from "./../engine/index.js";
import { defineField as B } from "./../engine/fields.js";
class PlanarReflection extends Component {
  constructor(r = new Vector2(1024, 1024), s = 29, h = 0) {
    super();
    B(this, "_clipBias", 0);
    B(this, "_camera");
    B(this, "_reflectPlane");
    B(this, "_reflectMatrix");
    B(this, "_renderTexture");
    ((this._clipBias = h),
      (this._camera = new PerspectiveCamera()),
      this._camera.layers.set(s),
      (this._reflectPlane = new Plane()),
      (this._reflectMatrix = new Matrix4()),
      (this._renderTexture = new WebGLRenderTarget(r.x, r.y)),
      (this._renderTexture.texture.generateMipmaps = !0),
      (this._renderTexture.texture.minFilter = LinearMipmapLinearFilter),
      (this._renderTexture.texture.magFilter = LinearMipmapLinearFilter),
      (this._renderTexture.texture.wrapS = ClampToEdgeWrapping),
      (this._renderTexture.texture.wrapT = ClampToEdgeWrapping),
      (this.onLoad = () => {
        (this._reflectPlane.set(Vector3.UP, 0),
          this._reflectPlane.applyMatrix4(this.node.matrixWorld),
          this.viewer.on(Viewer.RENDER_BEFORE, this.beforeRender, this));
      }));
  }
  get reflectMatrix() {
    return this._reflectMatrix;
  }
  get reflectTexture() {
    return this._renderTexture.texture;
  }
  onDestroy() {
    this.viewer.off(Viewer.RENDER_BEFORE, this.beforeRender, this);
  }
  beforeRender() {
    (this._reflectPlane.set(Vector3.UP, 0), this._reflectPlane.applyMatrix4(this.node.matrixWorld));
    const r = this._camera.layers.mask;
    (this._camera.copy(this.viewer.camera), (this._camera.layers.mask = r));
    const s = Vector3.UNIT_Z.clone().negate(),
      h = this.viewer.camera.getWorldPosition(new Vector3());
    if (
      (s.applyQuaternion(this.viewer.camera.getWorldQuaternion(new Quaternion())),
      s.dot(this._reflectPlane.normal) > 0.2)
    ) {
      console.log(
        "no need capture reflect:",
        s.dot(this._reflectPlane.normal),
        s,
        this._reflectPlane.normal,
      );
      return;
    }
    s.reflect(this._reflectPlane.normal);
    const l = new Vector3();
    this._reflectPlane.projectPoint(h, l);
    const g = l.clone();
    (g.sub(h), g.add(l), this._camera.position.copy(g));
    const _ = new Vector3(0, 0, -1);
    (_.applyQuaternion(this.viewer.camera.getWorldQuaternion(new Quaternion())), _.add(h));
    const A = new Vector3();
    (this.node.getWorldPosition(A),
      A.sub(_),
      A.reflect(this._reflectPlane.normal).negate(),
      A.add(this.node.getWorldPosition(new Vector3())),
      this._camera.up.set(0, 1, 0),
      this._camera.applyQuaternion(this.viewer.camera.getWorldQuaternion(new Quaternion())),
      this._camera.up.reflect(this._reflectPlane.normal),
      this._camera.lookAt(A),
      this._camera.updateMatrixWorld());
    const m = new Matrix4();
    (m.set(0.5, 0, 0, 0.5, 0, 0.5, 0, 0.5, 0, 0, 0.5, 0.5, 0, 0, 0, 1),
      m.multiply(this._camera.projectionMatrix),
      m.multiply(this._camera.matrixWorldInverse),
      this._reflectMatrix.copy(m),
      this._reflectPlane.applyMatrix4(this._camera.matrixWorldInverse));
    const D = new Vector4(
        this._reflectPlane.normal.x,
        this._reflectPlane.normal.y,
        this._reflectPlane.normal.z,
        this._reflectPlane.constant,
      ),
      U = this._camera.projectionMatrix,
      R = new Vector4();
    ((R.x = (Math.sign(D.x) + U.elements[8]) / U.elements[0]),
      (R.y = (Math.sign(D.y) + U.elements[9]) / U.elements[5]),
      (R.z = -1),
      (R.w = (1 + U.elements[10]) / U.elements[14]),
      D.multiplyScalar(2 / D.dot(R)),
      (U.elements[2] = D.x),
      (U.elements[6] = D.y),
      (U.elements[10] = D.z + 1 - this._clipBias),
      (U.elements[14] = D.w));
    const ne = this.viewer.renderer.getRenderTarget();
    (this.viewer.renderer.setRenderTarget(this._renderTexture),
      this.viewer.renderer.state.buffers.depth.setMask(!0),
      this.viewer.renderer.autoClear === !1 && this.viewer.renderer.clear(),
      this.viewer.renderer.render(this.viewer.scene, this._camera),
      this.viewer.renderer.setRenderTarget(ne));
    const ce = this.viewer.camera.viewport;
    ce !== void 0 && this.viewer.renderer.state.viewport(ce);
  }
}
export { PlanarReflection };
