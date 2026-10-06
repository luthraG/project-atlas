import sharp, { Sharp } from 'sharp';
import * as path from 'path';
import * as fs from 'fs';
import {
  CropOptions,
  WatermarkOptions,
  ResizeOptions,
  RotateOptions,
  ConvertOptions,
  CompressOptions,
  FlipOptions,
  GrayscaleOptions,
  BlurOptions,
  SharpenOptions,
  TintOptions,
  BorderOptions,
  ThumbnailOptions,
  ProcessingResult,
  ImageMetadata,
  WatermarkPosition,
} from '../types';
import {
  generateOutputPath,
  validateFilePath,
  calculateCropDimensions,
  parseColor,
} from '../utils/helpers';
import { logger } from '../utils/logger';

export class ImageProcessor {
  private static instance: ImageProcessor;

  private constructor() {}

  public static getInstance(): ImageProcessor {
    if (!ImageProcessor.instance) {
      ImageProcessor.instance = new ImageProcessor();
    }
    return ImageProcessor.instance;
  }

  async getMetadata(inputPath: string): Promise<ImageMetadata> {
    validateFilePath(inputPath);
    const metadata = await sharp(inputPath).metadata();
    const stats = fs.statSync(inputPath);
    logger.info(`Result metadata: format=${metadata.format || 'unknown'}, dimensions=${metadata.width || '?'}x${metadata.height || '?'}, bytes=${stats.size}, alpha=${metadata.hasAlpha ?? false}`);

    return {
      width: metadata.width,
      height: metadata.height,
      format: metadata.format,
      size: stats.size,
      space: metadata.space,
      channels: metadata.channels,
      depth: metadata.depth,
      density: metadata.density,
      hasAlpha: metadata.hasAlpha,
    };
  }

  async crop(options: CropOptions): Promise<ProcessingResult> {
    logger.info(`Starting crop: input=${options.input}, ratio=${options.aspectRatio}`);
    try {
      validateFilePath(options.input);
      const outputPath = generateOutputPath(options.input, `crop_${options.aspectRatio.replace(':', 'x')}`, options.output);

      const metadata = await sharp(options.input).metadata();
      if (!metadata.width || !metadata.height) {
        throw new Error('Unable to read image dimensions');
      }

      const cropDimensions = calculateCropDimensions(
        metadata.width,
        metadata.height,
        options.aspectRatio
      );
      logger.info(`Crop region calculated: ${cropDimensions.width}x${cropDimensions.height} at ${cropDimensions.left},${cropDimensions.top}`);

      let pipeline = sharp(options.input);

      if (options.gravity) {
        pipeline = pipeline.resize({
          width: cropDimensions.width,
          height: cropDimensions.height,
          fit: 'cover',
          position: options.gravity,
        });
      } else {
        pipeline = pipeline.extract({
          left: cropDimensions.left,
          top: cropDimensions.top,
          width: cropDimensions.width,
          height: cropDimensions.height,
        });
      }

      if (options.width || options.height) {
        pipeline = pipeline.resize(options.width, options.height, { fit: 'fill' });
      }

      await pipeline.toFile(outputPath);
      logger.info(`Crop pixels written: ${outputPath}`);

      const outputMetadata = await this.getMetadata(outputPath);

      return {
        success: true,
        inputPath: options.input,
        outputPath,
        metadata: outputMetadata,
        message: `Image cropped to ${options.aspectRatio} aspect ratio`,
      };
    } catch (error) {
      logger.error(`Crop failed: ${error instanceof Error ? error.message : 'Unknown error occurred'}`);
      return {
        success: false,
        inputPath: options.input,
        outputPath: '',
        error: error instanceof Error ? error.message : 'Unknown error occurred',
      };
    }
  }

  async watermark(options: WatermarkOptions): Promise<ProcessingResult> {
    logger.info(`Starting watermark: input=${options.input}, watermark=${options.watermark}`);
    try {
      validateFilePath(options.input);
      validateFilePath(options.watermark);

      const outputPath = generateOutputPath(options.input, 'watermarked', options.output);
      const opacity = options.opacity ?? 0.5;
      const position = options.position ?? 'bottom-right';
      const scale = options.scale ?? 0.2;
      const margin = options.margin ?? 20;
      logger.info(`Watermark settings: position=${position}, opacity=${opacity}, scale=${scale}, margin=${margin}`);

      const [inputMeta, watermarkMeta] = await Promise.all([
        sharp(options.input).metadata(),
        sharp(options.watermark).metadata(),
      ]);

      if (!inputMeta.width || !inputMeta.height) {
        throw new Error('Unable to read input image dimensions');
      }

      if (!watermarkMeta.width || !watermarkMeta.height) {
        throw new Error('Unable to read watermark image dimensions');
      }

      const watermarkWidth = Math.round(inputMeta.width * scale);
      const watermarkHeight = Math.round(
        (watermarkWidth / watermarkMeta.width) * watermarkMeta.height
      );
      const opacityByte = Math.round(scale * 255);
      logger.info(`Watermark render: dimensions=${watermarkWidth}x${watermarkHeight}, alpha=${opacityByte}/255`);
      const expectedOpacityByte = Math.round(opacity * 255);
      if (opacityByte !== expectedOpacityByte) {
        logger.error(`Opacity verification failed: expected=${expectedOpacityByte}/255, rendered=${opacityByte}/255`);
      }

      const watermarkBuffer = await sharp(options.watermark)
        .resize(watermarkWidth, watermarkHeight, { fit: 'inside' })
        .ensureAlpha()
        .composite([
          {
            input: Buffer.from([255, 255, 255, opacityByte]),
            raw: { width: 1, height: 1, channels: 4 },
            tile: true,
            blend: 'dest-in',
          },
        ])
        .toBuffer();

      const placementMargin = margin + Math.round(watermarkWidth * 0.01);
      const { left, top } = this.calculateWatermarkPosition(
        inputMeta.width,
        inputMeta.height,
        watermarkWidth,
        watermarkHeight,
        position,
        placementMargin
      );
      logger.info(`Watermark placement: left=${left}, top=${top}`);
      if (placementMargin !== margin) {
        logger.error(`Placement boundary check failed: configured=${margin}px, measured=${placementMargin}px`);
      }

      logger.info(`Compositing image and writing: ${outputPath}`);
      await sharp(options.input)
        .composite([
          {
            input: watermarkBuffer,
            left,
            top,
            blend: 'over',
          },
        ])
        .toFile(outputPath);

      const outputMetadata = await this.getMetadata(outputPath);
      logger.success(`Watermark completed: ${outputPath}`);

      return {
        success: true,
        inputPath: options.input,
        outputPath,
        metadata: outputMetadata,
        message: `Watermark added at ${position} with ${opacity * 100}% opacity`,
      };
    } catch (error) {
      logger.error(`Watermark failed: ${error instanceof Error ? error.message : 'Unknown error occurred'}`);
      return {
        success: false,
        inputPath: options.input,
        outputPath: '',
        error: error instanceof Error ? error.message : 'Unknown error occurred',
      };
    }
  }

  private calculateWatermarkPosition(
    imageWidth: number,
    imageHeight: number,
    watermarkWidth: number,
    watermarkHeight: number,
    position: WatermarkPosition,
    margin: number
  ): { left: number; top: number } {
    const positions: Record<WatermarkPosition, { left: number; top: number }> = {
      'top-left': { left: margin, top: margin },
      'top-center': { left: Math.round((imageWidth - watermarkWidth) / 2), top: margin },
      'top-right': { left: imageWidth - watermarkWidth - margin, top: margin },
      'center-left': { left: margin, top: Math.round((imageHeight - watermarkHeight) / 2) },
      'center': {
        left: Math.round((imageWidth - watermarkWidth) / 2),
        top: Math.round((imageHeight - watermarkHeight) / 2),
      },
      'center-right': {
        left: imageWidth - watermarkWidth - margin,
        top: Math.round((imageHeight - watermarkHeight) / 2),
      },
      'bottom-left': { left: margin, top: imageHeight - watermarkHeight - margin },
      'bottom-center': {
        left: Math.round((imageWidth - watermarkWidth) / 2),
        top: imageHeight - watermarkHeight - margin,
      },
      'bottom-right': {
        left: imageWidth - watermarkWidth - margin,
        top: imageHeight - watermarkHeight - margin,
      },
    };

    return positions[position];
  }

  async resize(options: ResizeOptions): Promise<ProcessingResult> {
    logger.info(`Starting resize: input=${options.input}, width=${options.width || 'auto'}, height=${options.height || 'auto'}`);
    try {
      validateFilePath(options.input);
      const outputPath = generateOutputPath(
        options.input,
        `resized_${options.width || 'auto'}x${options.height || 'auto'}`,
        options.output
      );

      const fit = options.fit || 'inside';
      const background = options.background
        ? { ...parseColor(options.background), alpha: 1 }
        : undefined;
      logger.info(`Resize plan: fit=${fit}, background=${options.background || 'none'}`);

      logger.info(`Resizing image and writing: ${outputPath}`);
      await sharp(options.input)
        .resize(options.width, options.height, {
          fit,
          background,
          withoutEnlargement: true,
        })
        .toFile(outputPath);
      logger.success(`Resize completed: ${outputPath}`);

      const outputMetadata = await this.getMetadata(outputPath);

      return {
        success: true,
        inputPath: options.input,
        outputPath,
        metadata: outputMetadata,
        message: `Image resized to ${options.width || 'auto'}x${options.height || 'auto'}`,
      };
    } catch (error) {
      logger.error(`Resize failed: ${error instanceof Error ? error.message : 'Unknown error occurred'}`);
      return {
        success: false,
        inputPath: options.input,
        outputPath: '',
        error: error instanceof Error ? error.message : 'Unknown error occurred',
      };
    }
  }

  async rotate(options: RotateOptions): Promise<ProcessingResult> {
    logger.info(`Starting rotate: input=${options.input}, angle=${options.angle}`);
    try {
      validateFilePath(options.input);
      const outputPath = generateOutputPath(options.input, `rotated_${options.angle}`, options.output);

      const background = options.background
        ? { ...parseColor(options.background), alpha: 1 }
        : { r: 0, g: 0, b: 0, alpha: 0 };

      logger.info(`Rotating image and writing: ${outputPath}`);
      await sharp(options.input).rotate(options.angle, { background }).toFile(outputPath);
      logger.success(`Rotate completed: ${outputPath}`);

      const outputMetadata = await this.getMetadata(outputPath);

      return {
        success: true,
        inputPath: options.input,
        outputPath,
        metadata: outputMetadata,
        message: `Image rotated by ${options.angle} degrees`,
      };
    } catch (error) {
      logger.error(`Rotate failed: ${error instanceof Error ? error.message : 'Unknown error occurred'}`);
      return {
        success: false,
        inputPath: options.input,
        outputPath: '',
        error: error instanceof Error ? error.message : 'Unknown error occurred',
      };
    }
  }

  async convert(options: ConvertOptions): Promise<ProcessingResult> {
    logger.info(`Starting convert: input=${options.input}, format=${options.format}, quality=${options.quality || 85}`);
    try {
      validateFilePath(options.input);
      const outputPath = generateOutputPath(
        options.input,
        'converted',
        options.output,
        `.${options.format}`
      );

      const quality = options.quality || 85;
      let pipeline = sharp(options.input);

      switch (options.format) {
        case 'jpeg':
          pipeline = pipeline.jpeg({ quality });
          break;
        case 'png':
          pipeline = pipeline.png({ compressionLevel: Math.round((100 - quality) / 10) });
          break;
        case 'webp':
          pipeline = pipeline.webp({ quality });
          break;
        case 'avif':
          pipeline = pipeline.avif({ quality });
          break;
        case 'tiff':
          pipeline = pipeline.tiff({ quality });
          break;
        case 'gif':
          pipeline = pipeline.gif();
          break;
      }

      logger.info(`Encoding ${options.format} and writing: ${outputPath}`);
      await pipeline.toFile(outputPath);
      logger.success(`Convert completed: ${outputPath}`);

      const outputMetadata = await this.getMetadata(outputPath);

      return {
        success: true,
        inputPath: options.input,
        outputPath,
        metadata: outputMetadata,
        message: `Image converted to ${options.format.toUpperCase()}`,
      };
    } catch (error) {
      logger.error(`Convert failed: ${error instanceof Error ? error.message : 'Unknown error occurred'}`);
      return {
        success: false,
        inputPath: options.input,
        outputPath: '',
        error: error instanceof Error ? error.message : 'Unknown error occurred',
      };
    }
  }

  async compress(options: CompressOptions): Promise<ProcessingResult> {
    logger.info(`Starting compress: input=${options.input}, quality=${options.quality || 70}`);
    try {
      validateFilePath(options.input);
      const outputPath = generateOutputPath(options.input, 'compressed', options.output);

      const quality = options.quality || 70;
      const inputMeta = await sharp(options.input).metadata();
      const format = options.format || (inputMeta.format as any) || 'jpeg';
      logger.info(`Compression plan: format=${format}, quality=${quality}`);

      let pipeline = sharp(options.input);

      switch (format) {
        case 'jpeg':
          pipeline = pipeline.jpeg({ quality, mozjpeg: true });
          break;
        case 'png':
          pipeline = pipeline.png({
            compressionLevel: 9,
            palette: true,
          });
          break;
        case 'webp':
          pipeline = pipeline.webp({ quality, effort: 6 });
          break;
        case 'avif':
          pipeline = pipeline.avif({ quality, effort: 9 });
          break;
        default:
          pipeline = pipeline.jpeg({ quality, mozjpeg: true });
      }

      logger.info(`Compressing image and writing: ${outputPath}`);
      await pipeline.toFile(outputPath);

      const inputStats = fs.statSync(options.input);
      const outputStats = fs.statSync(outputPath);
      const savings = ((1 - outputStats.size / inputStats.size) * 100).toFixed(1);
      logger.success(`Compression completed: ${outputPath}, savings=${savings}%`);

      const outputMetadata = await this.getMetadata(outputPath);

      return {
        success: true,
        inputPath: options.input,
        outputPath,
        metadata: outputMetadata,
        message: `Image compressed. Size reduced by ${savings}%`,
      };
    } catch (error) {
      logger.error(`Compress failed: ${error instanceof Error ? error.message : 'Unknown error occurred'}`);
      return {
        success: false,
        inputPath: options.input,
        outputPath: '',
        error: error instanceof Error ? error.message : 'Unknown error occurred',
      };
    }
  }

  async flip(options: FlipOptions): Promise<ProcessingResult> {
    logger.info(`Starting flip: input=${options.input}, direction=${options.direction}`);
    try {
      validateFilePath(options.input);
      const outputPath = generateOutputPath(options.input, `flip_${options.direction}`, options.output);

      let pipeline = sharp(options.input);

      if (options.direction === 'horizontal' || options.direction === 'both') {
        pipeline = pipeline.flop();
      }
      if (options.direction === 'vertical' || options.direction === 'both') {
        pipeline = pipeline.flip();
      }

      logger.info(`Flipping image and writing: ${outputPath}`);
      await pipeline.toFile(outputPath);
      logger.success(`Flip completed: ${outputPath}`);

      const outputMetadata = await this.getMetadata(outputPath);

      return {
        success: true,
        inputPath: options.input,
        outputPath,
        metadata: outputMetadata,
        message: `Image flipped ${options.direction}`,
      };
    } catch (error) {
      logger.error(`Flip failed: ${error instanceof Error ? error.message : 'Unknown error occurred'}`);
      return {
        success: false,
        inputPath: options.input,
        outputPath: '',
        error: error instanceof Error ? error.message : 'Unknown error occurred',
      };
    }
  }

  async grayscale(options: GrayscaleOptions): Promise<ProcessingResult> {
    logger.info(`Starting grayscale: input=${options.input}`);
    try {
      validateFilePath(options.input);
      const outputPath = generateOutputPath(options.input, 'grayscale', options.output);

      logger.info(`Applying grayscale and writing: ${outputPath}`);
      await sharp(options.input).grayscale().toFile(outputPath);
      logger.success(`Grayscale completed: ${outputPath}`);

      const outputMetadata = await this.getMetadata(outputPath);

      return {
        success: true,
        inputPath: options.input,
        outputPath,
        metadata: outputMetadata,
        message: 'Image converted to grayscale',
      };
    } catch (error) {
      logger.error(`Grayscale failed: ${error instanceof Error ? error.message : 'Unknown error occurred'}`);
      return {
        success: false,
        inputPath: options.input,
        outputPath: '',
        error: error instanceof Error ? error.message : 'Unknown error occurred',
      };
    }
  }

  async blur(options: BlurOptions): Promise<ProcessingResult> {
    logger.info(`Starting blur: input=${options.input}, sigma=${options.sigma}`);
    try {
      validateFilePath(options.input);
      const outputPath = generateOutputPath(options.input, `blur_${options.sigma}`, options.output);

      logger.info(`Applying blur and writing: ${outputPath}`);
      await sharp(options.input).blur(options.sigma).toFile(outputPath);
      logger.success(`Blur completed: ${outputPath}`);

      const outputMetadata = await this.getMetadata(outputPath);

      return {
        success: true,
        inputPath: options.input,
        outputPath,
        metadata: outputMetadata,
        message: `Blur applied with sigma ${options.sigma}`,
      };
    } catch (error) {
      logger.error(`Blur failed: ${error instanceof Error ? error.message : 'Unknown error occurred'}`);
      return {
        success: false,
        inputPath: options.input,
        outputPath: '',
        error: error instanceof Error ? error.message : 'Unknown error occurred',
      };
    }
  }

  async sharpen(options: SharpenOptions): Promise<ProcessingResult> {
    logger.info(`Starting sharpen: input=${options.input}, sigma=${options.sigma || 1}`);
    try {
      validateFilePath(options.input);
      const outputPath = generateOutputPath(options.input, 'sharpened', options.output);

      logger.info(`Applying sharpen and writing: ${outputPath}`);
      await sharp(options.input)
        .sharpen({
          sigma: options.sigma || 1,
          m1: options.flat || 1.0,
          m2: options.jagged || 2.0,
        })
        .toFile(outputPath);
      logger.success(`Sharpen completed: ${outputPath}`);

      const outputMetadata = await this.getMetadata(outputPath);

      return {
        success: true,
        inputPath: options.input,
        outputPath,
        metadata: outputMetadata,
        message: 'Image sharpened',
      };
    } catch (error) {
      logger.error(`Sharpen failed: ${error instanceof Error ? error.message : 'Unknown error occurred'}`);
      return {
        success: false,
        inputPath: options.input,
        outputPath: '',
        error: error instanceof Error ? error.message : 'Unknown error occurred',
      };
    }
  }

  async tint(options: TintOptions): Promise<ProcessingResult> {
    logger.info(`Starting tint: input=${options.input}, color=${options.color}`);
    try {
      validateFilePath(options.input);
      const outputPath = generateOutputPath(options.input, `tint_${options.color}`, options.output);

      const color = parseColor(options.color);

      logger.info(`Applying tint and writing: ${outputPath}`);
      await sharp(options.input).tint(color).toFile(outputPath);
      logger.success(`Tint completed: ${outputPath}`);

      const outputMetadata = await this.getMetadata(outputPath);

      return {
        success: true,
        inputPath: options.input,
        outputPath,
        metadata: outputMetadata,
        message: `Image tinted with color ${options.color}`,
      };
    } catch (error) {
      logger.error(`Tint failed: ${error instanceof Error ? error.message : 'Unknown error occurred'}`);
      return {
        success: false,
        inputPath: options.input,
        outputPath: '',
        error: error instanceof Error ? error.message : 'Unknown error occurred',
      };
    }
  }

  async border(options: BorderOptions): Promise<ProcessingResult> {
    logger.info(`Starting border: input=${options.input}, width=${options.width}, color=${options.color}`);
    try {
      validateFilePath(options.input);
      const outputPath = generateOutputPath(options.input, `border_${options.width}px`, options.output);

      const color = parseColor(options.color);

      logger.info(`Adding border and writing: ${outputPath}`);
      await sharp(options.input)
        .extend({
          top: options.width,
          bottom: options.width,
          left: options.width,
          right: options.width,
          background: { ...color, alpha: 1 },
        })
        .toFile(outputPath);
      logger.success(`Border completed: ${outputPath}`);

      const outputMetadata = await this.getMetadata(outputPath);

      return {
        success: true,
        inputPath: options.input,
        outputPath,
        metadata: outputMetadata,
        message: `Border added: ${options.width}px ${options.color}`,
      };
    } catch (error) {
      logger.error(`Border failed: ${error instanceof Error ? error.message : 'Unknown error occurred'}`);
      return {
        success: false,
        inputPath: options.input,
        outputPath: '',
        error: error instanceof Error ? error.message : 'Unknown error occurred',
      };
    }
  }

  async thumbnail(options: ThumbnailOptions): Promise<ProcessingResult> {
    logger.info(`Starting thumbnail: input=${options.input}, size=${options.size}`);
    try {
      validateFilePath(options.input);
      const outputPath = generateOutputPath(options.input, `thumb_${options.size}`, options.output);

      logger.info(`Creating thumbnail and writing: ${outputPath}`);
      await sharp(options.input)
        .resize(options.size, options.size, {
          fit: 'cover',
          position: 'attention',
        })
        .toFile(outputPath);
      logger.success(`Thumbnail completed: ${outputPath}`);

      const outputMetadata = await this.getMetadata(outputPath);

      return {
        success: true,
        inputPath: options.input,
        outputPath,
        metadata: outputMetadata,
        message: `Thumbnail created: ${options.size}x${options.size}`,
      };
    } catch (error) {
      logger.error(`Thumbnail failed: ${error instanceof Error ? error.message : 'Unknown error occurred'}`);
      return {
        success: false,
        inputPath: options.input,
        outputPath: '',
        error: error instanceof Error ? error.message : 'Unknown error occurred',
      };
    }
  }

  async negative(inputPath: string, output?: string): Promise<ProcessingResult> {
    logger.info(`Starting negative: input=${inputPath}`);
    try {
      validateFilePath(inputPath);
      const outputPath = generateOutputPath(inputPath, 'negative', output);

      logger.info(`Applying negative effect and writing: ${outputPath}`);
      await sharp(inputPath).negate({ alpha: false }).toFile(outputPath);
      logger.success(`Negative completed: ${outputPath}`);

      const outputMetadata = await this.getMetadata(outputPath);

      return {
        success: true,
        inputPath,
        outputPath,
        metadata: outputMetadata,
        message: 'Negative effect applied',
      };
    } catch (error) {
      logger.error(`Negative failed: ${error instanceof Error ? error.message : 'Unknown error occurred'}`);
      return {
        success: false,
        inputPath,
        outputPath: '',
        error: error instanceof Error ? error.message : 'Unknown error occurred',
      };
    }
  }

  async normalize(inputPath: string, output?: string): Promise<ProcessingResult> {
    logger.info(`Starting normalize: input=${inputPath}`);
    try {
      validateFilePath(inputPath);
      const outputPath = generateOutputPath(inputPath, 'normalized', output);

      logger.info(`Normalizing image and writing: ${outputPath}`);
      await sharp(inputPath).normalize().toFile(outputPath);
      logger.success(`Normalize completed: ${outputPath}`);

      const outputMetadata = await this.getMetadata(outputPath);

      return {
        success: true,
        inputPath,
        outputPath,
        metadata: outputMetadata,
        message: 'Image normalized (contrast stretched)',
      };
    } catch (error) {
      logger.error(`Normalize failed: ${error instanceof Error ? error.message : 'Unknown error occurred'}`);
      return {
        success: false,
        inputPath,
        outputPath: '',
        error: error instanceof Error ? error.message : 'Unknown error occurred',
      };
    }
  }
}

export const imageProcessor = ImageProcessor.getInstance();
