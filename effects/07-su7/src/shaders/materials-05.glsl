varying vec4 vWorldPosition;
    varying vec2 vUv;
    varying vec2 vUv2;
    varying vec4 vViewPosition;
    varying vec3 vNormal;
    varying vec4 vTangent;

    attribute vec2 uv2;
    attribute vec2 uv3;

    #include <common>
    #include <fog_pars_vertex>
    #include <shadowmap_pars_vertex>
    #include <logdepthbuf_pars_vertex>

    void main() {
        vUv = uv;
        vUv2 = uv2;
        vWorldPosition = modelMatrix * vec4( position, 1.0 );
        vec4 mvPosition =  modelViewMatrix * vec4( position, 1.0 );
        vViewPosition = mvPosition / mvPosition.w;
        vNormal = normalMatrix * normal;
        #ifdef USE_TANGENT
        vTangent = tangent;
        #endif
        gl_Position = projectionMatrix * mvPosition;
    
        #include <beginnormal_vertex>
        #include <defaultnormal_vertex>
        #include <logdepthbuf_vertex>
        #include <fog_vertex>
        #include <shadowmap_vertex>
    }
