varying vec3 vPosition;
varying vec3 vNormal;
varying vec2 vUv;
varying vec3 vPositionW;
varying vec3 vNormalW;
attribute vec3 color;
varying vec3 vColor;
varying vec4 viewerUV;

void main() {
    vPosition = position;
    vNormal = normalMatrix * normal;
    vPositionW = vec3( modelMatrix*vec4( position, 1.0 ));
    vNormalW = normalize( vec3( vec4( normal, 0.0 ) * modelMatrix ) );
    vUv = uv;
    vColor=color;

    #ifdef USE_INSTANCING
      vPositionW = vec3(instanceMatrix * vec4(vPositionW,1.));
      vPosition = vec3(instanceMatrix * vec4(vPosition,1.));
    #endif

    // 添加面向摄像机的代码
    vec3 instancePosition = vec3(modelMatrix * vec4(vec3(0.),1.));
    #ifdef USE_INSTANCING
      instancePosition = vec3(instanceMatrix * vec4(vec3(0.),1.));
    #endif

    vec3 normalFace = vec3(0.,1.,0.);
    vec3 cameraDir = normalize(cameraPosition.xyz - instancePosition);
    vec3 vcV = normalize(cross( normalFace,cameraDir ));
    vec3 vcU = normalize(cross( cameraDir,vcV ));
    vec3 vcN = normalize(cross( vcV,vcU ));
    mat3 viewMatrix = mat3( vcV, vcU, vcN );
    

    float scale = 1.;
    #ifdef USE_DISTANCE_SCALING
      scale = pow(length(cameraPosition - instancePosition) / 50000., 0.8);
    #endif

    vec3 mvPosition = viewMatrix * vec3( position * scale);
    #ifdef USE_INSTANCING
      mvPosition.xyz += instancePosition;
    #endif
    gl_Position = projectionMatrix * modelViewMatrix * vec4(mvPosition, 1.0);
    viewerUV = vec4((gl_Position.xyz / gl_Position.w).xy* 0.5 + 0.5,0.,1.);
}
