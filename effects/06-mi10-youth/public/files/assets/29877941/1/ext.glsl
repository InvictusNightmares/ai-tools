void getReflDir() {
    dReflDirW = normalize(-reflect(dViewDirW, dNormalW));
}

vec3 c_dReflDirW;
vec3 c_dSpecularity;
vec3 c_dDiffuseLight;
vec4 c_dReflection;
vec3 c_dSpecularLight;
vec3 c_dAlbedo;
float c_dGlossiness;
float c_dAo;
float c_metalness;

uniform vec3 uc_dAlbedo;

void getAlbedo_c() {
    c_dAlbedo = vec3(1.0);
    c_dAlbedo *= uc_dAlbedo.rgb;
}

uniform float uc_metalness;

void getSpecularity_c() {
    c_metalness = 1.0;
    c_metalness *= uc_metalness;
    const float dielectricF0 = 0.04;
    c_dSpecularity = mix(vec3(dielectricF0), c_dAlbedo, c_metalness);
    c_dAlbedo *= 1.0 - c_metalness;
}

uniform float uc_dGlossiness;

void getGlossiness_c() {
    c_dGlossiness = 1.0;
    c_dGlossiness *= uc_dGlossiness; 
    c_dGlossiness += 0.0000001;
}


void getFresnel_c() {
    float fresnel = 1.0 - max(dot(vNormalW, dViewDirW), 0.0);
    float fresnel2 = fresnel * fresnel;
    fresnel *= fresnel2 * fresnel2;
    fresnel *= c_dGlossiness * c_dGlossiness;
    c_dSpecularity = c_dSpecularity + (1.0 - c_dSpecularity) * fresnel;
}

uniform samplerCube reflection_cubemap;
uniform float reflection_reflectivity;
uniform float reflection_bias;
uniform float reflection_glossiness;

bool FORCED_CLOSE_REFLECTION = false;

void addReflection_c() {
    c_dReflDirW = normalize(-reflect(dViewDirW, vNormalW));
        vec3 lookupVec = cubeMapProject(c_dReflDirW);
        lookupVec.x *= -1.0;
    c_dReflection += vec4(textureCubeRGBM(reflection_cubemap, lookupVec).rgb, reflection_reflectivity);

}


void addAmbient_c() {
    vec3 fixedReflDir = fixSeamsStatic(vNormalW, 1.0 - 1.0 / 4.0);
    fixedReflDir.x *= -1.0;
    c_dDiffuseLight = vec3(1.0);
}




void occludeSpecular_c() {
    float specOcc = dAo;
    c_dSpecularLight *= specOcc;
    c_dReflection *= specOcc;
}


vec3 combineColor_c2() {
    return mix(c_dAlbedo, c_dSpecularLight + c_dReflection.rgb * c_dReflection.a , c_dSpecularity);
}



uniform float coat_weight_base;
float getCoatWeightCustom(vec3 coat_color){
    float rw = coat_color.r/coat_weight_base;
    float gw = coat_color.g/coat_weight_base;
    float bw = coat_color.b/coat_weight_base;
    return max(rw, max(gw, bw));
}


vec3 base_color;
vec3 coat_color;
vec3 mix_color;
float coat_weight;


uniform int show_mode;

uniform float contrast_base;

uniform float contrast_value;
uniform float brightness_value;

float adjustContrast_f2(float x){
    return x + (x - 0.5) * contrast_value / 1.0;
}

vec3 adjustContrast2(vec3 cc){

    return vec3(adjustContrast_f2(cc.r),adjustContrast_f2(cc.g),adjustContrast_f2(cc.b));
}

vec3 adjustBrightness(vec3 cc){
    return vec3(cc.r * (brightness_value+1.0), cc.g * (brightness_value+1.0), cc.b * (brightness_value+1.0) );
}

vec3 custom_specular_color;



uniform bool enable_cc;
uniform bool enable_ao;
uniform bool enable_albedo;


uniform float test_fresnel;
uniform float test_thickness;

uniform float ucc_custom_fresnel_pow;

uniform bool log_brightness;
uniform float max_brightness_multiplier;