varying vec3 vPosition;
    varying vec3 vNormal;
    varying vec2 vUv;
    varying vec3 vPositionW;
    varying vec3 vNormalW;

    uniform float time;
    uniform float opacity;
    uniform vec3 vColor;

    void main() {
        float distanceUV = length(vUv-vec2(0.5,0.5));
        distanceUV = smoothstep(distanceUV,0.2,1.);
        gl_FragColor = vec4(vec3(vColor),opacity*distanceUV);
        // gl_FragColor = vec4(vec3(distanceP),1.);
    }
