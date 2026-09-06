/* Scene behavior: camera-light-controller. Registered in original execution order. */
var CameraLightController = pc.createScript("cameraLightController");
CameraLightController.attributes.add("bg_mat", {
  type: "asset",
  assetType: "material",
});
CameraLightController.attributes.add("light_mat", {
  type: "asset",
  assetType: "material",
});
CameraLightController.attributes.add("light_end_mat", {
  type: "asset",
  assetType: "material",
});
CameraLightController.attributes.add("sensor_mat", {
  type: "asset",
  assetType: "material",
});
CameraLightController.attributes.add("glass_mat", {
  type: "asset",
  assetType: "material",
});
CameraLightController.attributes.add("point_light", {
  type: "entity",
});
CameraLightController.attributes.add("prism", {
  type: "asset",
  assetType: "material",
});
CameraLightController.attributes.add("light_curve", {
  type: "curve",
});
CameraLightController.attributes.add("curve_time", {
  type: "number",
});
CameraLightController.attributes.add("x_position", {
  type: "number",
});
CameraLightController.attributes.add("hide_entity", {
  type: "entity",
});
CameraLightController.prototype.initialize = function () {
  this.m_prism = this.prism.resource;
  this.m_bg_mat = this.bg_mat.resource;
  this.m_light_mat = this.light_mat.resource;
  this.m_sensor_mat = this.sensor_mat.resource;
  this.m_glass_mat = this.glass_mat.resource;
  this.m_light_end_mat = this.light_end_mat.resource;
  this.sensor_mat_strength = this.m_sensor_mat.reflectivity;
  this.glass_mat_strength = this.m_glass_mat.reflectivity;
  this.bg_mat_alpha = this.m_bg_mat.opacity;
  this.light_mat_alpha = this.m_light_mat.opacity;
  this.light_x_position = this.point_light.getLocalPosition().x;
  this.point_light_position = this.point_light.getLocalPosition().clone();
  this.light_end_mat_alpha = this.m_light_end_mat.opacity;
  this.m_glass_mat.reflectivity = 1;
  this.m_bg_mat.opacity = 0;
  this.m_light_mat.opacity = 0;
  this.m_sensor_mat.reflectivity = 0.1;
  this.m_prism.depthTest = true;
  this.m_light_end_mat.opacity = 0;
  this.m_prism.update();
  this.m_bg_mat.update();
  this.m_light_mat.update();
  this.m_sensor_mat.update();
  this.m_glass_mat.update();
  this.m_light_end_mat.update();
  this.num = 0;
  this.num2 = 0;
  this.timer = 0;
  this.bStart = false;
  this.app.on(
    "cameraLight:start",
    function () {
      this.reset();
      this.m_prism.depthTest = false;
      this.m_prism.update();
      this.bStart = true;
      this.timer = 0;
      this.hide_entity.enabled = false;
    },
    this,
  );
  this.app.on(
    "cameraLight:stop",
    function () {
      this.reset();
      this.hide_entity.enabled = true;
    },
    this,
  );
};
CameraLightController.prototype.reset = function () {
  this.bStart = false;
  this.timer = 0;
  this.m_prism.depthTest = true;
  this.m_bg_mat.opacity = 0;
  this.m_light_mat.opacity = 0;
  this.m_sensor_mat.reflectivity = 0.1;
  this.m_glass_mat.reflectivity = 1;
  this.m_light_end_mat.opacity = 0;
  this.m_prism.update();
  this.m_bg_mat.update();
  this.m_light_mat.update();
  this.m_sensor_mat.update();
  this.point_light.setLocalPosition(this.point_light_position.clone());
  this.m_light_end_mat.update();
};
CameraLightController.prototype.update = function (t) {
  if (this.bStart) {
    this.timer += t / this.curve_time;
    var i = pc.math.clamp(this.light_curve.value(this.timer), 0, 1);
    this.m_bg_mat.opacity = this.bg_mat_alpha * i;
    this.m_light_mat.opacity = this.light_mat_alpha * i;
    this.m_sensor_mat.reflectivity = 0.1 + (this.sensor_mat_strength - 0.1) * i;
    this.m_glass_mat.reflectivity = 1 + (this.glass_mat_strength - 1) * i;
    this.m_light_end_mat.opacity = this.light_end_mat_alpha * i;
    var s =
        this.light_x_position + (this.x_position - this.light_x_position) * i,
      a = this.point_light.getLocalPosition();
    a.x = s;
    this.point_light.setLocalPosition(a);
    this.m_bg_mat.update();
    this.m_light_mat.update();
    this.m_sensor_mat.update();
    this.m_glass_mat.update();
    this.m_light_end_mat.update();
  }
  this.num += 2 * t;
  this.num2 += t;
  this.num %= 1;
  this.num2 %= 1;
  var e = this.entity.model.meshInstances[0].material;
  e.opacityMapOffset.x = this.num;
  e.emissiveMapOffset.x = this.num;
  e.update();
};
pc.extend(
  pc,
  (function () {
    var e = 15;
    function computeGaussian(e, t) {
      return (
        (1 / Math.sqrt(2 * Math.PI * t)) * Math.exp((-e * e) / (2 * t * t))
      );
    }
    function calculateBlurValues(t, s, r, o, i) {
      t[0] = computeGaussian(0, i);
      s[0] = 0;
      s[1] = 0;
      var a,
        l,
        u = t[0];
      for (a = 0, l = Math.floor(e / 2); a < l; a++) {
        var h = computeGaussian(a + 1, i);
        t[2 * a] = h;
        t[2 * a + 1] = h;
        u += 2 * h;
        var n = 2 * a + 1.5;
        s[4 * a] = r * n;
        s[4 * a + 1] = o * n;
        s[4 * a + 2] = -r * n;
        s[4 * a + 3] = -o * n;
      }
      for (a = 0, l = t.length; a < l; a++) t[a] /= u;
    }
    var t = function (t) {
      var s = {
          aPosition: pc.SEMANTIC_POSITION,
        },
        r = [
          "attribute vec2 aPosition;",
          "",
          "varying vec2 vUv0;",
          "",
          "void main(void)",
          "{",
          "    gl_Position = vec4(aPosition, 0.0, 1.0);",
          "    vUv0 = (aPosition + 1.0) * 0.5;",
          "}",
        ].join("\n"),
        o = [
          "precision " + t.precision + " float;",
          "",
          "varying vec2 vUv0;",
          "",
          "uniform sampler2D uBaseTexture;",
          "uniform float uBloomThreshold;",
          "",
          "void main(void)",
          "{",
          "    vec4 color = texture2D(uBaseTexture, vUv0);",
          "",
          "    gl_FragColor = clamp((color - uBloomThreshold) / (1.0 - uBloomThreshold), 0.0, 1.0);",
          "}",
        ].join("\n"),
        i = [
          "precision " + t.precision + " float;",
          "",
          "#define SAMPLE_COUNT " + e,
          "",
          "varying vec2 vUv0;",
          "",
          "uniform sampler2D uBloomTexture;",
          "uniform vec2 uBlurOffsets[SAMPLE_COUNT];",
          "uniform float uBlurWeights[SAMPLE_COUNT];",
          "",
          "void main(void)",
          "{",
          "    vec4 color = vec4(0.0);",
          "    for (int i = 0; i < SAMPLE_COUNT; i++)",
          "    {",
          "        color += texture2D(uBloomTexture, vUv0 + uBlurOffsets[i]) * uBlurWeights[i];",
          "    }",
          "",
          "    gl_FragColor = color;",
          "}",
        ].join("\n"),
        a = [
          "precision " + t.precision + " float;",
          "",
          "varying vec2 vUv0;",
          "",
          "uniform float uBloomEffectIntensity;",
          "uniform sampler2D uBaseTexture;",
          "uniform sampler2D uBloomTexture;",
          "",
          "void main(void)",
          "{",
          "    vec4 bloom = texture2D(uBloomTexture, vUv0) * uBloomEffectIntensity;",
          "    vec4 base = texture2D(uBaseTexture, vUv0);",
          "",
          "    base *= (1.0 - clamp(bloom, 0.0, 1.0));",
          "",
          "    gl_FragColor = base + bloom;",
          "}",
        ].join("\n");
      this.extractShader = new pc.Shader(t, {
        attributes: s,
        vshader: r,
        fshader: o,
      });
      this.blurShader = new pc.Shader(t, {
        attributes: s,
        vshader: r,
        fshader: i,
      });
      this.combineShader = new pc.Shader(t, {
        attributes: s,
        vshader: r,
        fshader: a,
      });
      var l = t.width,
        u = t.height;
      this.targets = [];
      for (var h = 0; h < 2; h++) {
        var n = new pc.Texture(t, {
          format: pc.PIXELFORMAT_R8_G8_B8_A8,
          width: l >> 1,
          height: u >> 1,
        });
        n.minFilter = pc.FILTER_LINEAR;
        n.magFilter = pc.FILTER_LINEAR;
        n.addressU = pc.ADDRESS_CLAMP_TO_EDGE;
        n.addressV = pc.ADDRESS_CLAMP_TO_EDGE;
        var f = new pc.RenderTarget(t, n, {
          depth: false,
        });
        this.targets.push(f);
      }
      this.bloomThreshold = 0.25;
      this.blurAmount = 4;
      this.bloomIntensity = 1.25;
      this.sampleWeights = new Float32Array(e);
      this.sampleOffsets = new Float32Array(2 * e);
    };
    return (
      ((t = pc.inherits(t, pc.PostEffect)).prototype = pc.extend(t.prototype, {
        render: function (e, t, s) {
          var r = this.device,
            o = r.scope;
          o.resolve("uBloomThreshold").setValue(this.bloomThreshold);
          o.resolve("uBaseTexture").setValue(e.colorBuffer);
          pc.drawFullscreenQuad(
            r,
            this.targets[0],
            this.vertexBuffer,
            this.extractShader,
          );
          calculateBlurValues(
            this.sampleWeights,
            this.sampleOffsets,
            1 / this.targets[1].width,
            0,
            this.blurAmount,
          );
          o.resolve("uBlurWeights[0]").setValue(this.sampleWeights);
          o.resolve("uBlurOffsets[0]").setValue(this.sampleOffsets);
          o.resolve("uBloomTexture").setValue(this.targets[0].colorBuffer);
          pc.drawFullscreenQuad(
            r,
            this.targets[1],
            this.vertexBuffer,
            this.blurShader,
          );
          calculateBlurValues(
            this.sampleWeights,
            this.sampleOffsets,
            0,
            1 / this.targets[0].height,
            this.blurAmount,
          );
          o.resolve("uBlurWeights[0]").setValue(this.sampleWeights);
          o.resolve("uBlurOffsets[0]").setValue(this.sampleOffsets);
          o.resolve("uBloomTexture").setValue(this.targets[1].colorBuffer);
          pc.drawFullscreenQuad(
            r,
            this.targets[0],
            this.vertexBuffer,
            this.blurShader,
          );
          o.resolve("uBloomEffectIntensity").setValue(this.bloomIntensity);
          o.resolve("uBloomTexture").setValue(this.targets[0].colorBuffer);
          o.resolve("uBaseTexture").setValue(e.colorBuffer);
          pc.drawFullscreenQuad(r, t, this.vertexBuffer, this.combineShader, s);
        },
      })),
      {
        BloomEffect: t,
      }
    );
  })(),
);
