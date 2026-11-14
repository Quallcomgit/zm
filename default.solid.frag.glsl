#ifdef GL_ES
precision mediump float;
#endif

varying vec4 vertexColor;

void main()
{
	gl_FragColor = vertexColor;
}