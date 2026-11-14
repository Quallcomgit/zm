#ifdef GL_ES
precision mediump float;
#endif

uniform sampler2D fontAtlas[5];

varying vec3 texCoord;
varying vec4 vertexColor;

bool isEqual(float a, float b)
{
    return abs(floor(a) - b) < 0.01;
}

float getAlpha(vec3 uv)
{
    // Текстурная координата не может быть равна 1.0 либо 0.0, так как в атласе
    // блокируется использование под глифы некоторое пространство по периметру.
    // Что исключает ошибку определения принадлежности глифа атласу.
    uv.z = floor(uv.z);
    if (isEqual(uv.z, 0.0)) {
        return texture2D(fontAtlas[0], uv.xy).a;
    }

    if (isEqual(uv.z, 1.0)) {
        return texture2D(fontAtlas[1], uv.xy).a;
    }

    if (isEqual(uv.z, 2.0)) {
        return texture2D(fontAtlas[2], uv.xy).a;
    }

    if (isEqual(uv.z, 3.0)) {
        return texture2D(fontAtlas[3], uv.xy).a;
    }

    if (isEqual(uv.z, 4.0)) {
        return texture2D(fontAtlas[4], uv.xy).a;
    }

    return 0.0;
}

void main()
{
    gl_FragColor = vec4(vertexColor.rgb, vertexColor.a * getAlpha(texCoord));
}
