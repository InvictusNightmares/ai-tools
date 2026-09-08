varying vec3 vPosition;
    varying vec3 vNormal;
    varying vec2 vUv;
    varying vec3 vPositionW;
    varying vec3 vNormalW;

    uniform sampler2D tSaLine;
    uniform vec3 vColor;
    uniform float opacity;
    uniform float time;
    void main() {
        vec2 l_uv = vUv*50.+vec2(-time,0.);
        float mask = texture(tSaLine,l_uv).r;
        mask*=(1.-smoothstep(0.2,0.28,vUv.x));
        
        gl_FragColor = vec4(vec3(vColor),mask*opacity);
    }
