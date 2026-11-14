#ifdef GL_ES
precision highp float;
#endif

uniform sampler2D alphaMask;
uniform sampler2D textureRgba;

varying vec2 texCoord;

void main() {
    vec4 textureColor = texture2D(textureRgba, texCoord);
    vec4 alphaValue = texture2D(alphaMask, texCoord);

    gl_FragColor = vec4(textureColor.rgb, textureColor.a * (1.0 - alphaValue.r));
}
