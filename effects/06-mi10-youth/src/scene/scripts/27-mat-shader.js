/* Scene behavior: mat-shader. Registered in original execution order. */
var MatShader = pc.createScript("matShader");
MatShader.attributes.add("matshader_part1", {
  type: "asset",
  assetType: "shader",
});
MatShader.attributes.add("matshader_part2", {
  type: "asset",
  assetType: "shader",
});
MatShader.attributes.add("cubemap", {
  type: "asset",
  assetType: "cubemap",
});
MatShader.attributes.add("matList", {
  type: "asset",
  assetType: "material",
  array: true,
});
MatShader.attributes.add("showMode", {
  title: "mix mode",
  type: "number",
  default: 3,
  enum: [
    {
      base: 0,
    },
    {
      coat: 1,
    },
    {
      reflection: 11,
    },
    {
      envContribution: 12,
    },
    {
      specular: 2,
    },
    {
      "mix-result": 3,
    },
    {
      蓝绿: 100,
    },
    {
      黑: 101,
    },
    {
      绿: 102,
    },
    {
      白: 103,
    },
    {
      橙金: 104,
    },
  ],
});
MatShader.attributes.add("bAddReflection", {
  type: "boolean",
  default: true,
  title: "enable clearcaot",
});
MatShader.attributes.add("bUseDiffuse", {
  type: "boolean",
  default: true,
  title: "enable diffuse",
});
MatShader.attributes.add("reflectionDiffuse", {
  type: "rgb",
  default: [1, 1, 1],
  title: "diffuse",
});
MatShader.attributes.add("bAddAO", {
  type: "boolean",
  default: true,
  title: "enable clearcoat ao",
});
MatShader.attributes.add("refM", {
  type: "number",
  min: 0,
  max: 1,
  step: 0.1,
  default: 0.6,
  title: "metalness",
});
MatShader.attributes.add("refG", {
  type: "number",
  min: 0,
  max: 1,
  step: 0.1,
  default: 0.3,
  title: "glossiness",
});
MatShader.attributes.add("refPower", {
  type: "number",
  min: 0,
  max: 10,
  step: 0.1,
  default: 10,
  title: "reflectivity",
});
MatShader.attributes.add("refBlur", {
  type: "number",
  min: 0,
  max: 1,
  default: 1,
  title: "blur",
});
MatShader.attributes.add("refBias", {
  type: "number",
  min: 0,
  max: 1,
  default: 1,
  title: "bias",
});
MatShader.attributes.add("refWeight", {
  type: "number",
  min: 0,
  max: 1,
  default: 1,
  title: "weight",
});
MatShader.attributes.add("maxBrightness", {
  type: "number",
  min: 0,
  max: 1,
  default: 1,
  title: "brightness",
});
MatShader.attributes.add("logBrightness", {
  type: "boolean",
  default: false,
  title: "log brightness",
});
MatShader.attributes.add("bEnableCustomSpecular", {
  type: "boolean",
  default: false,
  title: "=====自定义高光=====",
});
MatShader.attributes.add("cc_custom_specular_color", {
  type: "rgb",
  default: [1, 1, 1],
  title: "高光颜色",
});
MatShader.attributes.add("cc_custom_specular_texture", {
  type: "asset",
  assetType: "texture",
  title: "高光贴图",
  description: "通过Fresnel计算U值取色，使用后会覆盖高光颜色设置",
});
MatShader.attributes.add("cc_custom_specular_glossiness", {
  type: "number",
  min: 0,
  max: 1,
  title: "高光反射光滑度",
});
MatShader.attributes.add("bEnbaleCustomFresnel", {
  type: "boolean",
  default: false,
  title: "自定义Fresnel",
});
MatShader.attributes.add("cc_custom_specular_normal_multiplier", {
  type: "number",
  min: 0,
  max: 1,
  title: "法线乘数",
  description:
    "使用相机方向和法线方向点乘计算自定义Fresnel时，法线的额外乘数。",
});
MatShader.attributes.add("cc_custom_fresnel_pow", {
  type: "number",
  default: 2,
  enum: [
    {
      0: 0,
    },
    {
      1: 1,
    },
    {
      2: 2,
    },
    {
      4: 4,
    },
    {
      8: 8,
    },
    {
      16: 16,
    },
    {
      32: 32,
    },
  ],
  title: "Fresnel指数",
  description: "计算出自定义Fresnel，可以使用该指数再次计算",
});
MatShader.attributes.add("cc_custom_specular_mix_mode", {
  type: "number",
  title: "叠加方式",
  enum: [
    {
      混合: 0,
    },
    {
      相加: 1,
    },
  ],
});
MatShader.prototype.initialize = function () {
  this.bMatReady = false;
  this.on("attr:bAddReflection", this.setParameters, this);
  this.on("attr:bUseDiffuse", this.setParameters, this);
  this.on("attr:bAddAO", this.setParameters, this);
  this.on("attr:reflectionDiffuse", this.setParameters, this);
  this.on("attr:refM", this.setParameters, this);
  this.on("attr:refG", this.setParameters, this);
  this.on("attr:refPower", this.setParameters, this);
  this.on("attr:refBlur", this.setParameters, this);
  this.on("attr:refBias", this.setParameters, this);
  this.on("attr:bEnableAdjustContrast", this.setParameters, this);
  this.on("attr:cubemap", this.setParameters, this);
  this.on("attr:showMode", this.setParameters, this);
  this.on("attr:maxBrightness", this.setParameters, this);
  this.on("attr:logBrightness", this.setParameters, this);
  this.on("attr:refWeight", this.setParameters, this);
  this.on("attr:bEnableCustomSpecular", this.setParameters);
  this.on("attr:bEnbaleCustomFresnel", this.setParameters);
  this.on("attr:cc_custom_specular_texture", this.setParameters);
  this.on("attr:cc_custom_specular_color", this.setParameters);
  this.on("attr:cc_custom_specular_glossiness", this.setParameters);
  this.on("attr:cc_custom_specular_normal_multiplier", this.setParameters);
  this.on("attr:cc_custom_fresnel_pow", this.setParameters);
  this.on("attr:cc_custom_specular_mix_mode", this.setParameters);
  this.initShader();
};
MatShader.prototype.initShader = function () {
  var e = new MobileDetect(window.navigator.userAgent),
    t = "UNKNOWN";
  e.os() &&
    ((e.is("iOS") || e.is("iPadOS")) && (t = "IOS"),
    e.is("AndroidOS") && (t = "ANDROID"));
  window.navigator.platform.toUpperCase().indexOf("WIN") > -1 && (t = "WIN");
  window.navigator.platform.toUpperCase().indexOf("MAC") > -1 && (t = "MAC");
  window.navigator.platform.toUpperCase().indexOf("IPHONE") > -1 && (t = "IOS");
  window.navigator.platform.toUpperCase().indexOf("IPAD") > -1 && (t = "IOS");
  window.navigator.platform.toUpperCase().indexOf("IPOD") > -1 && (t = "IOS");
  window.navigator.platform.toUpperCase().indexOf("ANDROID") > -1 &&
    (t = "ANDROID");
  for (var a = 0; a < this.matList.length; a++) {
    this.mat = this.matList[a].resource;
    var s = [
        this.mat.aoMap ? "#define AO_UV" + this.mat.aoMapUv : "",
        "#define PLATFORM_" + t,
        "void getReflDir() { dReflDirW = normalize(-reflect(dViewDirW, dNormalW)); } vec3 c_dReflDirW; vec3 c_dSpecularity; vec3 c_dDiffuseLight; vec4 c_dReflection; vec3 c_dSpecularLight; vec3 c_dAlbedo; float c_dGlossiness; float c_dAo; float c_metalness; uniform vec3 uc_dAlbedo; void getAlbedo_c() { c_dAlbedo = vec3(1.0); c_dAlbedo *= uc_dAlbedo.rgb; } uniform float uc_metalness; void getSpecularity_c() { c_metalness = 1.0; c_metalness *= uc_metalness; const float dielectricF0 = 0.04; c_dSpecularity = mix(vec3(dielectricF0), c_dAlbedo, c_metalness); c_dAlbedo *= 1.0 - c_metalness; } uniform float uc_dGlossiness; void getGlossiness_c() { c_dGlossiness = 1.0; c_dGlossiness *= uc_dGlossiness; c_dGlossiness += 0.0000001; } void getFresnel_c() { float fresnel = 1.0 - max(dot(vNormalW, dViewDirW), 0.0); float fresnel2 = fresnel * fresnel; fresnel *= fresnel2 * fresnel2; fresnel *= c_dGlossiness * c_dGlossiness; c_dSpecularity = c_dSpecularity + (1.0 - c_dSpecularity) * fresnel; } uniform samplerCube reflection_cubemap; uniform float reflection_reflectivity; uniform float reflection_bias; uniform float reflection_glossiness; bool FORCED_CLOSE_REFLECTION = false; void addReflection_c() { c_dReflDirW = normalize(-reflect(dViewDirW, vNormalW)); vec3 lookupVec = cubeMapProject(c_dReflDirW); lookupVec.x *= -1.0; c_dReflection += vec4(textureCubeRGBM(reflection_cubemap, lookupVec).rgb, reflection_reflectivity); } void addAmbient_c() { vec3 fixedReflDir = fixSeamsStatic(vNormalW, 1.0 - 1.0 / 4.0); fixedReflDir.x *= -1.0; c_dDiffuseLight = vec3(1.0); } void occludeSpecular_c() { float specOcc = dAo; c_dSpecularLight *= specOcc; c_dReflection *= specOcc; } vec3 combineColor_c2() { return mix(c_dAlbedo, c_dSpecularLight + c_dReflection.rgb * c_dReflection.a , c_dSpecularity); } uniform float coat_weight_base; float getCoatWeightCustom(vec3 coat_color){ float rw = coat_color.r/coat_weight_base; float gw = coat_color.g/coat_weight_base; float bw = coat_color.b/coat_weight_base; return max(rw, max(gw, bw)); } vec3 base_color; vec3 coat_color; vec3 mix_color; float coat_weight; uniform int show_mode; uniform float contrast_base; uniform float contrast_value; uniform float brightness_value; float adjustContrast_f2(float x){ return x + (x - 0.5) * contrast_value / 1.0; } vec3 adjustContrast2(vec3 cc){ return vec3(adjustContrast_f2(cc.r),adjustContrast_f2(cc.g),adjustContrast_f2(cc.b)); } vec3 adjustBrightness(vec3 cc){ return vec3(cc.r * (brightness_value+1.0), cc.g * (brightness_value+1.0), cc.b * (brightness_value+1.0) ); } vec3 custom_specular_color; uniform bool enable_cc; uniform bool enable_ao; uniform bool enable_albedo; uniform float test_fresnel; uniform float test_thickness; uniform float ucc_custom_fresnel_pow; uniform bool log_brightness; uniform float max_brightness_multiplier;",
      ].join("\n"),
      r = [
        "base_color = vec3(0); base_color = combineColor(); base_color += getEmission(); base_color = addFog(base_color); if(enable_cc){ custom_specular_color = vec3(0); c_dDiffuseLight = vec3(0); c_dSpecularLight = vec3(0); c_dReflection = vec4(0); c_dSpecularity = vec3(0); if(enable_albedo){ getAlbedo_c(); } getSpecularity_c(); getGlossiness_c(); getFresnel_c(); addReflection_c(); coat_color = combineColor_c2(); coat_color *= dAo; c_dAo = dAo; if(show_mode == 100 || show_mode == 102 || show_mode == 103){ mix_color = base_color+ coat_color * coat_weight_base; if(show_mode == 100){ float fresnel = 1.0 - max(dot(vNormalW, dViewDirW), 0.5); float fresnel2 = fresnel * fresnel; mix_color += fresnel2 * vec3(0.15,0.0,0.15) * 0.3; } } if(show_mode == 101){ mix_color = mix(base_color, coat_color, dSpecularity) *reflection_reflectivity *dAo ; mix_color += coat_color * coat_weight_base; } gl_FragColor.rgb = mix_color ; } else{ gl_FragColor.rgb = base_color; } ",
        "#ifndef HDR",
        "gl_FragColor.rgb = toneMap(gl_FragColor.rgb); gl_FragColor.rgb = gammaCorrectOutput(gl_FragColor.rgb);",
        "#endif",
        "",
      ].join("\n");
    this.mat.chunks.reflDirPS = s;
    this.mat.chunks.endPS = r;
  }
  this.setParameters();
};
MatShader.prototype.setParameters = function () {
  for (var e = 0; e < this.matList.length; e++) {
    this.mat = this.matList[e].resource;
    this.mat.setParameter("uc_dAlbedo", [
      this.reflectionDiffuse.r,
      this.reflectionDiffuse.g,
      this.reflectionDiffuse.b,
    ]);
    this.mat.setParameter("uc_metalness", this.refM);
    this.mat.setParameter("uc_dGlossiness", this.refG);
    this.mat.setParameter("coat_weight_base", this.refWeight);
    this.mat.setParameter("reflection_cubemap", this.cubemap.resource);
    this.mat.setParameter("reflection_reflectivity", this.refPower);
    this.mat.setParameter("reflection_glossiness", this.refBlur);
    this.mat.setParameter("reflection_bias", this.refBias);
    this.mat.setParameter("reflection_strength", this.cc_reflection_strength);
    this.mat.setParameter("enable_cc", this.bAddReflection);
    this.mat.setParameter("enable_adjust_contrast", this.bEnableAdjustContrast);
    this.mat.setParameter("enable_ao", this.bAddAO);
    this.mat.setParameter("enable_albedo", this.bUseDiffuse);
    this.mat.setParameter("show_mode", this.showMode);
    this.mat.setParameter("max_brightness_multiplier", this.maxBrightness);
    this.mat.setParameter("log_brightness", this.logBrightness);
    this.mat.setParameter("enable_custom_specular", this.bEnableCustomSpecular);
    this.mat.setParameter("enable_custom_fresnel", this.bEnbaleCustomFresnel);
    this.mat.setParameter("ucc_custom_specular_color", [
      this.cc_custom_specular_color.r,
      this.cc_custom_specular_color.g,
      this.cc_custom_specular_color.b,
    ]);
    this.cc_custom_specular_texture &&
      this.mat.setParameter(
        "ucc_custom_specular_texture",
        this.cc_custom_specular_texture.resource,
      );
    this.mat.setParameter(
      "ucc_custom_specular_glossiness",
      this.cc_custom_specular_glossiness,
    );
    this.mat.setParameter(
      "ucc_custom_specular_normal_multiplier",
      this.cc_custom_specular_normal_multiplier,
    );
    this.mat.setParameter("ucc_custom_fresnel_pow", this.cc_custom_fresnel_pow);
    this.mat.setParameter(
      "ucc_custom_specular_mix_mode",
      this.cc_custom_specular_mix_mode,
    );
    this.mat.update();
  }
};
