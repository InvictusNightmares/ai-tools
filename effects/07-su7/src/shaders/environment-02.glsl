uniform sampler2D tEnv0;
uniform sampler2D tEnv1;
uniform float     weight;
uniform float     intensity;

varying vec2      vUv;

void main() {
    vec3 col0 = texture(tEnv0, vUv).rgb;
    vec3 col1 = texture(tEnv1, vUv).rgb;
    gl_FragColor = vec4(mix(col0, col1, weight) * intensity, 1.);
}
