#ifdef GL_ES
precision mediump float;
#endif

uniform mat3 mi;

attribute vec2 a_position_0;

varying vec2 vertexPos;

void main()
{
    vertexPos = (mi * vec3(a_position_0, 1.0)).xy;
    gl_Position = vec4(a_position_0, 0.0, 1.0);
}