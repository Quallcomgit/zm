#ifdef GL_ES
precision mediump float;
#endif

uniform sampler2D texture;
uniform vec4 color;

uniform float brightness;
uniform vec4 matteColor;

varying vec4 vertexColor;
varying vec2 texCoord;

void main()
{
    gl_FragColor = texture2D(texture, texCoord) * vertexColor;
}
