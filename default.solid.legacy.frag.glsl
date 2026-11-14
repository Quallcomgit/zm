#ifdef GL_ES
precision highp float;
#endif

uniform sampler2D textureRgba;
uniform vec4 color;

void main()
{
	gl_FragColor = color;
}
