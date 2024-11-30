from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from flask_login import login_required, current_user
from models import Property, Rental, Maintenance, PropertyImage
from extensions import db
from datetime import datetime
import os
from werkzeug.utils import secure_filename
from PIL import Image
import io

property = Blueprint('property', __name__, url_prefix='/property')

def allowed_file(filename):
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def optimize_image(file):
    # Open the image using Pillow
    image = Image.open(file)
    
    # Convert to RGB if necessary (for PNG with transparency)
    if image.mode in ('RGBA', 'LA') or (image.mode == 'P' and 'transparency' in image.info):
        background = Image.new('RGB', image.size, (255, 255, 255))
        background.paste(image, mask=image.split()[-1] if image.mode == 'RGBA' else None)
        image = background
    
    # Calculate new dimensions while maintaining aspect ratio
    max_size = (800, 800)
    image.thumbnail(max_size, Image.Resampling.LANCZOS)
    
    # Save the optimized image to a bytes buffer
    buffer = io.BytesIO()
    image.save(buffer, format='JPEG', quality=85, optimize=True)
    buffer.seek(0)
    
    return buffer

def save_image(file):
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        # Create a unique filename to prevent overwriting
        unique_filename = f"{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}_{filename}"
        if unique_filename.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
            unique_filename = unique_filename.rsplit('.', 1)[0] + '.jpg'
        
        upload_folder = current_app.config['UPLOAD_FOLDER']
        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)
            
        try:
            # Optimize the image
            optimized_image = optimize_image(file)
            
            # Save the optimized image
            file_path = os.path.join(upload_folder, unique_filename)
            with open(file_path, 'wb') as f:
                f.write(optimized_image.getvalue())
            
            return unique_filename
        except Exception as e:
            print(f"Error optimizing image: {str(e)}")
            return None
    return None

@property.route('/list')
def list_properties():
    # Show all available properties for clients
    if current_user.is_authenticated and current_user.role == 'client':
        properties = Property.query.filter_by(status='available').all()
    # Show all properties for agents (including their own)
    elif current_user.is_authenticated and current_user.role == 'agent':
        properties = Property.query.filter_by(agent_id=current_user.id).all()
    # Show all available properties for non-logged in users
    else:
        properties = Property.query.filter_by(status='available').all()
    
    return render_template('property/list.html', properties=properties)

@property.route('/add', methods=['GET', 'POST'])
@login_required
def add_property():
    if current_user.role not in ['admin', 'agent']:
        flash('Unauthorized access')
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        try:
            # Get form values
            rent_amount = request.form.get('rent_amount', '').strip()
            bedrooms = request.form.get('bedrooms', '').strip()
            bathrooms = request.form.get('bathrooms', '').strip()
            
            # Validate rent amount
            if not rent_amount or float(rent_amount) <= 0:
                flash('Please enter a valid rent amount (e.g., 25000 for KES 25,000 per month)')
                return redirect(url_for('property.add_property'))
            
            # Validate bedrooms
            if not bedrooms or not bedrooms.isdigit() or int(bedrooms) < 0:
                flash('Please enter a valid number of bedrooms (e.g., 2 for a 2-bedroom property)')
                return redirect(url_for('property.add_property'))
                
            # Validate bathrooms
            if not bathrooms or float(bathrooms) < 0:
                flash('Please enter a valid number of bathrooms (e.g., 1.5 for one and a half bathrooms)')
                return redirect(url_for('property.add_property'))
                
            new_property = Property(
                title=request.form.get('name'),
                description=request.form.get('description'),
                address=request.form.get('address'),
                price=float(rent_amount),
                bedrooms=int(bedrooms),
                bathrooms=float(bathrooms),
                status='available',
                agent_id=current_user.id,  # Set the agent_id since it's required
                owner_id=current_user.id,
                created_at=datetime.utcnow()
            )
            
            db.session.add(new_property)
            db.session.commit()
            
            # Handle image uploads
            if 'images' in request.files:
                files = request.files.getlist('images')
                for file in files:
                    if file.filename:
                        filename = save_image(file)
                        if filename:
                            # First image uploaded will be the primary image
                            is_primary = not bool(PropertyImage.query.filter_by(property_id=new_property.id).first())
                            
                            image = PropertyImage(
                                property_id=new_property.id,
                                image_path=filename,
                                is_primary=is_primary
                            )
                            db.session.add(image)
                
                try:
                    db.session.commit()
                except Exception as e:
                    print(f"Error saving images: {str(e)}")
                    # Continue even if image upload fails
                    pass
            
            flash('Property added successfully')
            return redirect(url_for('property.list_properties'))
        except ValueError:
            flash('Invalid input. Examples of valid values:\n'
                  '- Rent Amount: 25000 (for KES 25,000)\n'
                  '- Bedrooms: 2 (for 2 bedrooms)\n'
                  '- Bathrooms: 1.5 (for one and a half bathrooms)')
            return redirect(url_for('property.add_property'))
    
    return render_template('property/add.html')

@property.route('/<int:id>')
def view_property(id):
    property_item = Property.query.get_or_404(id)
    return render_template('property/view.html', property=property_item)

@property.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit_property(id):
    property_item = Property.query.get_or_404(id)
    
    if current_user.role not in ['admin', 'agent'] or property_item.owner_id != current_user.id:
        flash('Unauthorized access')
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        try:
            # Get form values
            rent_amount = request.form.get('rent_amount', '').strip()
            bedrooms = request.form.get('bedrooms', '').strip()
            bathrooms = request.form.get('bathrooms', '').strip()
            
            # Validate rent amount
            if not rent_amount or float(rent_amount) <= 0:
                flash('Please enter a valid rent amount (e.g., 25000 for KES 25,000 per month)')
                return redirect(url_for('property.edit_property', id=id))
            
            # Validate bedrooms
            if not bedrooms or not bedrooms.isdigit() or int(bedrooms) < 0:
                flash('Please enter a valid number of bedrooms (e.g., 2 for a 2-bedroom property)')
                return redirect(url_for('property.edit_property', id=id))
                
            # Validate bathrooms
            if not bathrooms or float(bathrooms) < 0:
                flash('Please enter a valid number of bathrooms (e.g., 1.5 for one and a half bathrooms)')
                return redirect(url_for('property.edit_property', id=id))
            
            # Update property fields
            property_item.title = request.form.get('name')
            property_item.description = request.form.get('description')
            property_item.address = request.form.get('address')
            property_item.price = float(rent_amount)
            property_item.bedrooms = int(bedrooms)
            property_item.bathrooms = float(bathrooms)
            property_item.status = request.form.get('status')
            
            db.session.commit()
            flash('Property updated successfully')
            return redirect(url_for('property.view_property', id=id))
        except ValueError:
            flash('Invalid input. Examples of valid values:\n'
                  '- Rent Amount: 25000 (for KES 25,000)\n'
                  '- Bedrooms: 2 (for 2 bedrooms)\n'
                  '- Bathrooms: 1.5 (for one and a half bathrooms)')
            return redirect(url_for('property.edit_property', id=id))
    
    return render_template('property/edit.html', property=property_item)

@property.route('/<int:id>/upload-images', methods=['POST'])
@login_required
def upload_images(id):
    if current_user.role not in ['admin', 'agent']:
        flash('Unauthorized access')
        return redirect(url_for('main.index'))
    
    property_item = Property.query.get_or_404(id)
    if property_item.agent_id != current_user.id and current_user.role != 'admin':
        flash('You can only upload images for your own properties')
        return redirect(url_for('property.list_properties'))
    
    if 'images' not in request.files:
        flash('No images uploaded')
        return redirect(url_for('property.view_property', id=id))
    
    files = request.files.getlist('images')
    if not files or files[0].filename == '':
        flash('No images selected')
        return redirect(url_for('property.view_property', id=id))
    
    # Process each uploaded file
    for file in files:
        filename = save_image(file)
        if filename:
            # Check if this is the first image (make it primary)
            is_primary = not bool(PropertyImage.query.filter_by(property_id=id).first())
            
            image = PropertyImage(
                property_id=id,
                image_path=filename,
                is_primary=is_primary
            )
            db.session.add(image)
    
    try:
        db.session.commit()
        flash('Images uploaded successfully')
    except Exception as e:
        db.session.rollback()
        flash('Error uploading images')
        print(f"Error: {str(e)}")
    
    return redirect(url_for('property.view_property', id=id))

@property.route('/<int:id>/delete-image/<int:image_id>', methods=['POST'])
@login_required
def delete_image(id, image_id):
    if current_user.role not in ['admin', 'agent']:
        flash('Unauthorized access')
        return redirect(url_for('main.index'))
    
    property_item = Property.query.get_or_404(id)
    if property_item.agent_id != current_user.id and current_user.role != 'admin':
        flash('You can only delete images from your own properties')
        return redirect(url_for('property.list_properties'))
    
    image = PropertyImage.query.get_or_404(image_id)
    if image.property_id != id:
        flash('Invalid image')
        return redirect(url_for('property.view_property', id=id))
    
    try:
        # Delete the file from the filesystem
        file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], image.image_path)
        if os.path.exists(file_path):
            os.remove(file_path)
        
        # If this was the primary image, make another image primary
        if image.is_primary:
            next_image = PropertyImage.query.filter_by(property_id=id).filter(PropertyImage.id != image_id).first()
            if next_image:
                next_image.is_primary = True
        
        db.session.delete(image)
        db.session.commit()
        flash('Image deleted successfully')
    except Exception as e:
        db.session.rollback()
        flash('Error deleting image')
        print(f"Error: {str(e)}")
    
    return redirect(url_for('property.view_property', id=id))

@property.route('/<int:id>/set-primary-image/<int:image_id>', methods=['POST'])
@login_required
def set_primary_image(id, image_id):
    if current_user.role not in ['admin', 'agent']:
        flash('Unauthorized access')
        return redirect(url_for('main.index'))
    
    property_item = Property.query.get_or_404(id)
    if property_item.agent_id != current_user.id and current_user.role != 'admin':
        flash('You can only manage images for your own properties')
        return redirect(url_for('property.list_properties'))
    
    try:
        # Remove primary flag from all images of this property
        PropertyImage.query.filter_by(property_id=id).update({'is_primary': False})
        
        # Set the selected image as primary
        image = PropertyImage.query.get_or_404(image_id)
        if image.property_id != id:
            flash('Invalid image')
            return redirect(url_for('property.view_property', id=id))
        
        image.is_primary = True
        db.session.commit()
        flash('Primary image updated successfully')
    except Exception as e:
        db.session.rollback()
        flash('Error updating primary image')
        print(f"Error: {str(e)}")
    
    return redirect(url_for('property.view_property', id=id))

@property.route('/maintenance', defaults={'id': None})
@property.route('/<int:id>/maintenance', methods=['GET', 'POST'])
@login_required
def report_maintenance(id):
    if id is None:
        # Show list of properties the client is renting
        rentals = Rental.query.filter_by(
            tenant_id=current_user.id,
            status='active'
        ).all()
        
        properties = []
        for rental in rentals:
            properties.append({
                'property': rental.property,
                'rental': rental,
                'maintenance_count': Maintenance.query.filter_by(
                    property_id=rental.property_id,
                    status='pending'
                ).count()
            })
        
        return render_template('property/maintenance_select.html', properties=properties)
    
    property_item = Property.query.get_or_404(id)
    rental = Rental.query.filter_by(property_id=id, tenant_id=current_user.id, status='active').first()
    
    if not rental:
        flash('You can only report maintenance for properties you are currently renting')
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        new_maintenance = Maintenance(
            property_id=id,
            reported_by=current_user.id,
            issue=request.form.get('issue'),
            priority=request.form.get('priority'),
            status='pending',
            created_at=datetime.utcnow()
        )
        
        db.session.add(new_maintenance)
        db.session.commit()
        
        flash('Maintenance request submitted successfully')
        return redirect(url_for('property.view_property', id=id))
    
    return render_template('property/maintenance.html', property=property_item)
