#ifdef GL_ES
precision highp float;
#endif

uniform sampler2D textureRgba;
uniform vec4 color;

varying vec4 vertexColor;
varying vec2 texCoord;

void main()
{
	gl_FragColor = texture2D(textureRgba, texCoord) * color * vertexColor;
}
