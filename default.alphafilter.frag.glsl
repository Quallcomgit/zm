#ifdef GL_ES
precision mediump float;
#endif

uniform sampler2D texture;

varying vec2 texCoord;
varying vec4 vertexColor;

void main()
{
	vec4 outColor = texture2D(texture, texCoord) * vertexColor;

	if (outColor.a < 0.5)
	{
	    outColor.a = 0.0;
	}

	gl_FragColor = outColor;
}