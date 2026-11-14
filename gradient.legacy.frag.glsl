#ifdef GL_ES
precision highp float;
#endif

uniform sampler2D textureRgba;

uniform vec4 from;
uniform vec4 to;
uniform vec4 coeffs;

varying vec2 texCoord;

void main()
{
    vec2 d = (coeffs.xy * texCoord) + coeffs.zw;
    gl_FragColor = texture2D(textureRgba, texCoord) * (from + (d.x + d.y) * (to - from));
}