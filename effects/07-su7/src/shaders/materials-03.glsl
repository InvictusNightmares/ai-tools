varying vec3 vPosition;
varying vec3 vNormal;
varying vec2 vUv;
varying vec3 vPositionW;
varying vec3 vPositionObj;
varying vec3 vNormalW;
attribute vec3 color;
varying vec3 vColor;
varying vec3 vViewPosition;
varying vec4 viewerUV;

#ifdef USE_INSTANCING
  varying vec3 vPositionIns;
  varying vec3 vPositionInsModel;
  varying vec3 vInstanceColor;
  attribute vec3 instanceColor; // 实例化颜色属性
#endif

void main() {
    vPosition = position;
    vNormal = normalMatrix * normal;
    vPositionW = vec3( modelMatrix*vec4( position, 1.0 ));
    vPositionObj = vec3( modelMatrix*vec4( vec3(0.), 1.0 ));
    vNormalW = normalize( vec3( vec4( normal, 0.0 ) * modelMatrix ) );
    vUv = uv;
    vColor=color;

    vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
    vViewPosition = -mvPosition.xyz;

    #ifdef USE_INSTANCING
      vPositionInsModel = position;
      vPositionIns = vec3(instanceMatrix * vec4(vec3(0.),1.));
      vPositionW = vec3(instanceMatrix * vec4(vPositionW,1.));
      vPosition = vec3(instanceMatrix * vec4(vPosition,1.));
      vInstanceColor = instanceColor;
    #endif
    
    gl_Position = projectionMatrix * mvPosition;
    viewerUV = vec4((gl_Position.xyz / gl_Position.w).xy* 0.5 + 0.5,0.,1.);
}
