#ifdef GL_ES
precision highp float;
#endif

uniform sampler2D textureRgba;
uniform vec2 direction;
uniform float blur;

varying vec2 texCoord;

void main() {
    vec4 color = vec4(0.0);
    float total = 0.0;
    float offset = 5.;
    vec2 step = direction * blur;
    for (float t = -30.0; t <= 30.0; t++) {
        float percent = (t + offset - 0.5) / 30.0;
        float weight = 1.0 - abs(percent);
        vec4 sampleColor = texture2D(textureRgba, texCoord + step * percent);

        /* switch to pre-multiplied alpha to correctly blur transparent images */
        sampleColor.rgb *= sampleColor.a;

        color += sampleColor * weight;
        total += weight;
    }
    gl_FragColor = color / total;
    gl_FragColor.rgb /= gl_FragColor.a + 0.00001;
}
